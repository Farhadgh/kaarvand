"""Tool execution service: validate -> policy -> dispatch -> audit."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.executor import execute_connector_tool
from app.core.errors import AppError
from app.db.models import McpServer, Tool, ToolInvocation
from app.db.session import get_session_factory, set_tenant
from app.tools.builtin import run_builtin
from app.tools.http_exec import execute_http_tool
from app.tools.mcp import call_tool as mcp_call_tool
from app.tools.policy import decide
from app.tools.schema import validate_arguments


async def _dispatch(
    db: AsyncSession,
    tool: Tool,
    args: dict[str, Any],
    run_id: uuid.UUID | None,
    org_id: uuid.UUID,
) -> dict[str, Any]:
    if tool.kind == "builtin":
        return await run_builtin(tool.slug, args, tool)
    if tool.kind == "http":
        return await execute_http_tool(tool, args)
    if tool.kind == "mcp":
        server_id = (tool.config or {}).get("mcp_server_id")
        if not server_id:
            raise AppError(code="mcp.server_not_configured", status_code=422)
        server = await db.get(McpServer, uuid.UUID(str(server_id)))
        if server is None:
            raise AppError(code="mcp.server_not_found", status_code=422)
        remote_name = (tool.config or {}).get("remote_name") or tool.slug
        return await mcp_call_tool(server, str(remote_name), args)
    if tool.kind == "connector":
        return await execute_connector_tool(
            db,
            tool=tool,
            args=args,
            org_id=org_id,
            run_id=run_id,
            timeout=float((tool.config or {}).get("timeout") or 60.0),
        )
    raise AppError(code="tool.unknown_kind", status_code=422, params={"kind": tool.kind})


async def _persist_invocation(invocation: ToolInvocation, org_id: uuid.UUID) -> str:
    """Audit in its own transaction so failures are recorded even if the caller rolls back."""
    factory = get_session_factory()
    async with factory() as session:
        await set_tenant(session, org_id)
        session.add(invocation)
        await session.flush()
        invocation_id = str(invocation.id)
        await session.commit()
    return invocation_id


async def execute_tool(
    db: AsyncSession,
    *,
    tool: Tool,
    args: dict[str, Any],
    org_id: uuid.UUID,
    permission_level: str = "auto",
    run_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run one tool call. ``force=True`` is only for the admin "test" button."""
    validate_arguments(tool.input_schema, args)

    decision = decide(
        risk_level=tool.risk_level,
        permission_level=permission_level,
        approval_policy=tool.approval_policy,
        is_enabled=tool.is_enabled,
    )
    if not force:
        if not decision.allowed:
            raise AppError(
                code=decision.code or "tool.denied",
                status_code=403,
                params={"tool": tool.slug, "risk": tool.risk_level},
            )
        if decision.needs_approval:
            raise AppError(
                code="tool.approval_required",
                status_code=409,
                params={"tool": tool.slug, "risk": tool.risk_level},
            )

    started = time.perf_counter()
    invocation = ToolInvocation(
        org_id=org_id,
        run_id=run_id,
        tool_id=tool.id,
        tool_slug=tool.slug,
        args=args,
        result={},
        status="ok",
        risk_level=tool.risk_level,
        approved_by=user_id if force else None,
    )

    try:
        result = await _dispatch(db, tool, args, run_id, org_id)
    except Exception as exc:
        invocation.status = "error"
        invocation.result = {
            "error": getattr(exc, "code", "tool.failed"),
            "detail": str(exc)[:500],
        }
        invocation.latency_ms = int((time.perf_counter() - started) * 1000)
        await _persist_invocation(invocation, org_id)
        raise

    invocation.result = result
    invocation.latency_ms = int((time.perf_counter() - started) * 1000)
    invocation_id = await _persist_invocation(invocation, org_id)

    return {"ok": True, "result": result, "invocation_id": invocation_id}
