"""Agent execution engine.

A DB-persisted tool-calling loop (no hidden framework state):

    system prompt (rendered from the prompt table)
    -> model stream -> tool calls -> policy/approval -> tool result -> model ...
    -> final answer, cost in the usage ledger, resumable approval state

Everything the panel needs to show (tokens, cost in Toman, each tool call) is
written to ``runs`` / ``messages`` / ``usage_ledger`` / ``tool_invocations``.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.service import effective_prompt
from app.billing.cost import price_model_usage
from app.billing.fx import current_fx_rate
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    Agent,
    Conversation,
    Message,
    Model,
    Organization,
    Provider,
    Run,
    UsageLedger,
    User,
)
from app.db.session import set_tenant
from app.providers.gateway import stream_model
from app.runtime.budget import check_run_tokens, ensure_budget
from app.runtime.events import event
from app.runtime.tools_binding import BoundTool, load_bound_tools
from app.tools.policy import decide
from app.tools.service import execute_tool

MAX_STEPS = 8
HISTORY_LIMIT = 10


class RunEngine:
    def __init__(
        self,
        db: AsyncSession,
        *,
        run: Run,
        user_id: uuid.UUID,
        settings: Settings,
        input_text: str = "",
        conversation_id: uuid.UUID | None = None,
        approved: bool = False,
        max_tokens: int | None = None,
    ) -> None:
        self.db = db
        self.run = run
        self.user_id = user_id
        self.settings = settings
        self.input_text = input_text
        self.conversation_id = conversation_id
        self.approved = approved
        self.max_tokens = max_tokens

        # plain ids: the engine commits/rolls back, so ORM instances can expire
        self.org_id: uuid.UUID = run.org_id
        self.agent_id: uuid.UUID | None = run.agent_id

        # loaded in _initialise (inside the engine's own session)
        self.user: User | None = None
        self.agent: Agent | None = None
        self.org: Organization | None = None

        self._state: dict[str, Any] = dict(run.state or {})
        self._approval_requested = False
        self._conversation: Conversation | None = None
        self.fx_rate: int = int(settings.fx_usd_irr)

    # --- helpers ----------------------------------------------------------
    async def _commit(self) -> None:
        """Commit and re-bind the tenant (``SET LOCAL`` dies with the transaction)."""
        self._save_state()
        await self.db.commit()
        await set_tenant(self.db, self.org_id)

    def _save_state(self) -> None:
        """Force a JSONB change: assigning the *same* dict is not detected."""
        self.run.state = dict(self._state)
        flag_modified(self.run, "state")

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._state.setdefault("messages", [])

    async def _model(self) -> Model:
        if not self.agent or not self.agent.model_id:
            raise AppError(code="agent.model_required", status_code=409)
        model = await self.db.get(Model, self.agent.model_id)
        if model is None:
            raise AppError(code="model.not_found", status_code=409)
        if not model.is_enabled:
            raise AppError(
                code="model.disabled",
                status_code=409,
                params={"model": model.external_id},
            )
        provider = await self.db.get(Provider, model.provider_id)
        if provider is None or not provider.is_enabled:
            raise AppError(code="provider.disabled", status_code=409)
        return model

    def _append_tool_result(self, call_id: str, payload: dict[str, Any]) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(payload, ensure_ascii=False, default=str)[:8000],
            }
        )

    async def _load_context(self) -> None:
        if not self.agent_id:
            raise AppError(code="agent.not_found", status_code=409)
        self.agent = await self.db.get(Agent, self.agent_id)
        self.org = await self.db.get(Organization, self.org_id)
        self.user = await self.db.get(User, self.user_id)
        if self.agent is None:
            raise AppError(code="agent.not_found", status_code=409)
        if self.org is None:
            raise AppError(code="org.not_found", status_code=409)
        if self.user is None:
            raise AppError(code="auth.user_not_found", status_code=409)

        raw_conversation = self._state.get("conversation_id") or self.conversation_id
        if raw_conversation:
            self._conversation = await self.db.get(
                Conversation, uuid.UUID(str(raw_conversation))
            )

    async def _initialise(self) -> None:
        await self._load_context()
        assert self.agent is not None and self.org is not None and self.user is not None
        self.fx_rate = await current_fx_rate(self.db, self.settings)
        prompt = await effective_prompt(self.db, user=self.user, agent=self.agent)
        await ensure_budget(self.db, agent=self.agent, org_budget_irr=self.org.monthly_budget_irr)

        conversation = None
        raw_id = self.conversation_id or self._state.get("conversation_id")
        if raw_id:
            conversation = await self.db.get(Conversation, uuid.UUID(str(raw_id)))
        if conversation is None:
            conversation = Conversation(
                org_id=self.org_id,
                agent_id=self.agent_id,
                user_id=self.user_id,
                channel="web",
                title=(self.input_text or "Ø§Ø¬Ø±Ø§")[:80],
            )
            self.db.add(conversation)
            await self.db.flush()
        self._conversation = conversation
        self._state["conversation_id"] = str(conversation.id)

        history: list[dict[str, Any]] = []
        if self.agent.memory_mode != "none":
            rows = (
                (
                    await self.db.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at.desc())
                        .limit(HISTORY_LIMIT)
                    )
                )
                .scalars()
                .all()
            )
            history = [
                {"role": row.role, "content": row.content}
                for row in reversed(rows)
                if row.role in {"user", "assistant"} and row.content
            ]

        self._state["messages"] = [
            {"role": "system", "content": prompt["rendered"]},
            *history,
            {"role": "user", "content": self.input_text},
        ]
        self._state.setdefault("pending", [])
        self._state["prompt_version"] = prompt["version"]

        self.db.add(Message(conversation_id=conversation.id, role="user", content=self.input_text))
        self._save_state()
        self.run.status = "running"
        self.run.started_at = self.run.started_at or datetime.now(UTC)
        await self._commit()

    # --- main loop --------------------------------------------------------
    async def events(self) -> AsyncIterator[dict[str, Any]]:
        yield event(
            "run.started",
            {"run_id": str(self.run.id), "status": self.run.status},
        )
        try:
            if not self._state.get("messages"):
                await self._initialise()
            else:
                if self.agent is None:
                    await self._load_context()
                    await set_tenant(self.db, self.org_id)
            async for item in self._loop():
                yield item
        except AppError as exc:
            await self._fail(exc.code, dict(exc.params))
            yield event("run.failed", {"code": exc.code, "params": exc.params})
        except Exception as exc:  # noqa: BLE001 - surfaced as a stable code
            await self._fail("run.internal_error", {"detail": str(exc)[:300]})
            yield event("run.failed", {"code": "run.internal_error", "detail": str(exc)[:300]})

    async def _loop(self) -> AsyncIterator[dict[str, Any]]:
        model = await self._model()
        bound, schemas, index = await load_bound_tools(self.db, self.agent)
        total_in = self.run.tokens_in
        total_out = self.run.tokens_out
        final_text = ""

        if self._state.get("pending"):
            async for item in self._execute_pending(bound, index):
                yield item

        while self.run.steps_taken < MAX_STEPS:
            self.run.steps_taken += 1
            yield event("llm.start", {"step": self.run.steps_taken, "model": model.external_id})

            text_parts: list[str] = []
            calls: dict[int, dict[str, Any]] = {}
            tokens_in = tokens_out = 0

            async for chunk in stream_model(
                self.db,
                model=model,
                messages=self.messages,
                tools=schemas or None,
                temperature=float(self.agent.temperature),
                max_tokens=self.agent.max_tokens,
            ):
                if chunk.type == "text" and chunk.text:
                    text_parts.append(chunk.text)
                    yield event("token", {"text": chunk.text})
                elif chunk.type == "tool_call" and chunk.tool_call:
                    self._merge_call(calls, chunk.tool_call)
                elif chunk.type == "usage":
                    tokens_in = chunk.tokens_in or 0
                    tokens_out = chunk.tokens_out or 0
                elif chunk.type == "notice":
                    yield event("notice", {"code": chunk.error_code, "detail": chunk.detail})
                elif chunk.type == "error":
                    raise AppError(
                        chunk.error_code or "provider.call_failed",
                        status_code=502,
                        params={"detail": chunk.detail},
                    )

            total_in += tokens_in
            total_out += tokens_out
            self.run.tokens_in, self.run.tokens_out = total_in, total_out
            check_run_tokens(total_in, total_out, self.max_tokens)

            content = "".join(text_parts)
            if calls:
                normalized = [calls[key] for key in sorted(calls)]
                self.messages.append(
                    {"role": "assistant", "content": content or None, "tool_calls": normalized}
                )
                async for item in self._handle_calls(normalized, bound, index):
                    yield item

                if self._approval_requested:
                    await self._wait_for_approval()
                    yield event(
                        "run.waiting_approval",
                        {
                            "run_id": str(self.run.id),
                            "pending": self._state.get("pending", []),
                        },
                    )
                    return
                continue

            self.messages.append({"role": "assistant", "content": content})
            final_text = content
            break
        else:
            raise AppError("run.max_steps", status_code=409, params={"max_steps": MAX_STEPS})

        await self._finish(model, total_in, total_out, final_text)
        yield event(
            "run.completed",
            {
                "run_id": str(self.run.id),
                "text": final_text,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "cost_usd": str(self.run.cost_usd),
                "cost_irr": self.run.cost_irr,
                "fx_rate": self.fx_rate,
                "steps": self.run.steps_taken,
            },
        )

    @staticmethod
    def _merge_call(calls: dict[int, dict[str, Any]], delta: dict[str, Any]) -> None:
        position = int(delta.get("index") or 0)
        entry = calls.setdefault(
            position,
            {"id": None, "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if delta.get("id"):
            entry["id"] = delta["id"]
        if delta.get("name"):
            entry["function"]["name"] += str(delta["name"])
        if delta.get("arguments"):
            entry["function"]["arguments"] += str(delta["arguments"])
        if not entry["id"]:
            entry["id"] = f"call_{position}"

    async def _handle_calls(
        self,
        calls: list[dict[str, Any]],
        bound: dict[str, BoundTool],
        index: dict[str, str],
    ) -> AsyncIterator[dict[str, Any]]:
        self._approval_requested = False

        for call in calls:
            call_id = call.get("id") or "call_0"
            name = (call.get("function") or {}).get("name") or ""
            slug = index.get(name)
            raw_args = (call.get("function") or {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}

            if slug is None or slug not in bound:
                self._append_tool_result(call_id, {"error": "tool.not_bound", "tool": name})
                yield event("tool.error", {"code": "tool.not_bound", "tool": name})
                continue

            binding = bound[slug]
            decision = decide(
                risk_level=binding.tool.risk_level,
                permission_level=binding.permission_level,
                approval_policy=binding.tool.approval_policy,
                is_enabled=binding.tool.is_enabled,
            )

            if not decision.allowed:
                self._append_tool_result(call_id, {"error": decision.code})
                yield event("tool.denied", {"tool": slug, "code": decision.code})
                continue

            if decision.needs_approval and not self.approved:
                self._state.setdefault("pending", []).append(
                    {"id": call_id, "name": name, "arguments": raw_args, "slug": slug}
                )
                self._approval_requested = True
                yield event(
                    "approval.required",
                    {
                        "tool": slug,
                        "risk": binding.tool.risk_level,
                        "arguments": args,
                        "call_id": call_id,
                    },
                )
                continue

            yield event("tool.call", {"tool": slug, "arguments": args})

            try:
                outcome = await execute_tool(
                    self.db,
                    tool=binding.tool,
                    args=args,
                    org_id=self.org_id,
                    permission_level=binding.permission_level,
                    run_id=self.run.id,
                    user_id=self.user_id,
                    force=self.approved,
                )
            except AppError as exc:
                self._append_tool_result(call_id, {"error": exc.code, "params": exc.params})
                yield event("tool.error", {"tool": slug, "code": exc.code})
                continue

            self._append_tool_result(call_id, outcome["result"])
            yield event(
                "tool.result",
                {
                    "tool": slug,
                    "result": outcome["result"],
                    "invocation_id": outcome.get("invocation_id"),
                },
            )

    async def _execute_pending(
        self, bound: dict[str, BoundTool], index: dict[str, str]
    ) -> AsyncIterator[dict[str, Any]]:
        pending = list(self._state.get("pending") or [])
        self._state["pending"] = []

        for item in pending:
            slug = str(item.get("slug") or "")
            call_id = str(item.get("id") or "call_0")
            binding = bound.get(slug)
            try:
                args = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if binding is None:
                self._append_tool_result(call_id, {"error": "tool.not_bound"})
                continue

            yield event("tool.call", {"tool": slug, "arguments": args, "approved": True})
            try:
                outcome = await execute_tool(
                    self.db,
                    tool=binding.tool,
                    args=args if isinstance(args, dict) else {},
                    org_id=self.org_id,
                    permission_level=binding.permission_level,
                    run_id=self.run.id,
                    user_id=self.user_id,
                    force=True,
                )
            except AppError as exc:
                self._append_tool_result(call_id, {"error": exc.code})
                yield event("tool.error", {"tool": slug, "code": exc.code})
                continue

            self._append_tool_result(call_id, outcome["result"])
            yield event(
                "tool.result",
                {"tool": slug, "result": outcome["result"], "approved": True},
            )

    async def _wait_for_approval(self) -> None:
        self.run.status = "waiting_approval"
        self._save_state()
        await self._commit()

    async def _finish(self, model: Model, tokens_in: int, tokens_out: int, final_text: str) -> None:
        cost_usd, cost_irr = price_model_usage(
            model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            fx_rate=self.fx_rate,
        )
        self.run.cost_usd = cost_usd
        self.run.cost_irr = cost_irr
        self.run.fx_rate = Decimal(str(self.fx_rate))
        self.run.tokens_in = tokens_in
        self.run.tokens_out = tokens_out
        self.run.status = "completed"
        self.run.finished_at = datetime.now(UTC)
        self._state["pending"] = []
        self._state["messages"] = self.messages[-12:]
        self._save_state()

        if self._conversation is not None and final_text:
            self.db.add(
                Message(
                    conversation_id=self._conversation.id,
                    role="assistant",
                    content=final_text,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_irr=cost_irr,
                )
            )

        self.db.add(
            UsageLedger(
                org_id=self.org_id,
                agent_id=self.agent_id,
                provider_id=model.provider_id,
                model_id=model.id,
                run_id=self.run.id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                markup_percent=Decimal(str(model.markup_percent or 0)),
                fx_rate=Decimal(str(self.fx_rate)),
                cost_irr=cost_irr,
                billable=not self.settings.free_mode,
            )
        )
        await self._commit()

    async def _fail(self, code: str, params: dict[str, Any]) -> None:
        self.run.status = "failed"
        self.run.error_code = code
        self.run.error_message = json.dumps(params, ensure_ascii=False)[:800]
        self.run.finished_at = datetime.now(UTC)
        self._save_state()
        try:
            await self._commit()
        except Exception:  # noqa: BLE001 - never mask the original failure
            await self.db.rollback()
