"""Tool registry API (HTTP / MCP / connector / builtin)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_agent
from app.core.deps import get_current_user, get_db, require_roles
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.db.models import AgentTool, McpServer, Tool, User
from app.schemas.tools import (
    ActionOpOut,
    LlmToolOut,
    McpServerCreate,
    McpServerOut,
    McpSyncOut,
    ToolCreate,
    ToolOut,
    ToolTestIn,
    ToolTestOut,
    ToolUpdate,
)
from app.tools.actions import catalog as action_catalog
from app.tools.actions import validate_actions
from app.tools.builtin import BUILTINS
from app.tools.http_exec import ALLOWED_METHODS
from app.tools.mcp import list_tools as mcp_list_tools
from app.tools.schema import to_llm_tool, validate_schema_definition
from app.tools.secrets import encrypt_tool_secret, masked_secret
from app.tools.service import execute_tool

router = APIRouter(tags=["tools"])
editor = require_roles("owner", "admin", "operator")


def to_out(tool: Tool) -> ToolOut:
    data = ToolOut.model_validate(tool)
    data.has_secret = bool(tool.secret_enc)
    try:
        data.secret_masked = masked_secret(tool)
    except Exception:  # noqa: BLE001 - a wrong master key must not break listing
        data.secret_masked = None
    return data


async def get_tool(db: AsyncSession, user: User, tool_id: uuid.UUID) -> Tool:
    tool = (
        await db.execute(
            select(Tool).where(
                Tool.id == tool_id,
                or_(Tool.org_id == user.org_id, Tool.org_id.is_(None)),
            )
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError(code="tool.not_found")
    return tool


def _ensure_editable(tool: Tool) -> None:
    if tool.org_id is None:
        raise ForbiddenError(code="tool.global_readonly")


def validate_tool_payload(
    *,
    kind: str,
    slug: str,
    config: dict[str, Any],
    actions: list[dict[str, Any]],
    input_schema: dict[str, Any],
) -> None:
    validate_schema_definition(input_schema)

    if kind == "builtin":
        if slug not in BUILTINS:
            raise AppError(
                code="tool.unknown_builtin",
                status_code=422,
                params={"slug": slug, "available": sorted(BUILTINS)},
            )
        return

    if kind == "http":
        if not config.get("url"):
            raise AppError(code="tool.missing_url", status_code=422)
        method = str(config.get("method") or "GET").upper()
        if method not in ALLOWED_METHODS:
            raise AppError(
                code="tool.method_not_allowed", status_code=422, params={"method": method}
            )
        if not config.get("allowed_domains"):
            raise AppError(code="tool.domain_not_configured", status_code=422)
        return

    if kind == "mcp":
        if not config.get("mcp_server_id"):
            raise AppError(code="mcp.server_not_configured", status_code=422)
        return

    if kind == "connector":
        if not actions:
            raise AppError(
                code="tool.invalid_actions", status_code=422, params={"reason": "no_actions"}
            )
        validate_actions(actions)


@router.get("/tools/ops", response_model=list[ActionOpOut])
async def list_action_ops(_: User = Depends(get_current_user)) -> list[ActionOpOut]:
    return [ActionOpOut(**row) for row in action_catalog()]


@router.get("/tools", response_model=list[ToolOut])
async def list_tools(
    kind: str | None = None,
    category: str | None = None,
    enabled_only: bool = True,
    q: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ToolOut]:
    stmt = select(Tool).where(or_(Tool.org_id == user.org_id, Tool.org_id.is_(None)))
    if kind:
        stmt = stmt.where(Tool.kind == kind)
    if category:
        stmt = stmt.where(Tool.category == category)
    if enabled_only:
        stmt = stmt.where(Tool.is_enabled.is_(True))
    if q:
        stmt = stmt.where(Tool.slug.ilike(f"%{q}%") | Tool.name_fa.ilike(f"%{q}%"))
    rows = (await db.execute(stmt.order_by(Tool.org_id.is_(None), Tool.slug))).scalars().all()
    return [to_out(row) for row in rows]


@router.post("/tools", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
async def create_tool(
    payload: ToolCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> ToolOut:
    validate_tool_payload(
        kind=payload.kind,
        slug=payload.slug,
        config=payload.config,
        actions=payload.actions,
        input_schema=payload.input_schema,
    )

    duplicate = (
        await db.execute(
            select(Tool.id).where(Tool.org_id == user.org_id, Tool.slug == payload.slug)
        )
    ).first()
    if duplicate is not None:
        raise AppError(code="tool.duplicate_slug", status_code=409, params={"slug": payload.slug})

    tool = Tool(
        org_id=user.org_id,
        slug=payload.slug,
        name_fa=payload.name_fa,
        description_fa=payload.description_fa,
        kind=payload.kind,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        config=payload.config,
        actions=payload.actions,
        risk_level=payload.risk_level,
        approval_policy=payload.approval_policy,
        category=payload.category,
        is_enabled=payload.is_enabled,
        secret_label=payload.secret_label,
        created_by=user.id,
    )
    db.add(tool)
    await db.flush()
    tool.secret_enc = encrypt_tool_secret(tool, payload.secret)
    await db.flush()
    return to_out(tool)


@router.get("/tools/llm-schemas", response_model=list[LlmToolOut])
async def agent_tool_schemas(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LlmToolOut]:
    """The exact tool payload an agent would send to the model."""
    agent = await get_agent(db, user, agent_id)
    rows = (
        (
            await db.execute(
                select(Tool)
                .join(AgentTool, AgentTool.tool_id == Tool.id)
                .where(
                    AgentTool.agent_id == agent.id,
                    AgentTool.is_enabled.is_(True),
                    Tool.is_enabled.is_(True),
                )
                .order_by(Tool.slug)
            )
        )
        .scalars()
        .all()
    )

    out: list[LlmToolOut] = []
    for tool in rows:
        payload = to_llm_tool(tool)
        function = payload["function"]
        out.append(
            LlmToolOut(
                name=function["name"],
                description=function["description"],
                parameters=function["parameters"],
                slug=tool.slug,
            )
        )
    return out


@router.post("/tools/{tool_id}/test", response_model=ToolTestOut)
async def test_tool(
    tool_id: uuid.UUID,
    payload: ToolTestIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> ToolTestOut:
    tool = await get_tool(db, user, tool_id)
    outcome = await execute_tool(
        db,
        tool=tool,
        args=payload.arguments,
        org_id=user.org_id,
        user_id=user.id,
        force=True,
    )
    return ToolTestOut(
        ok=True,
        result=outcome["result"],
        invocation_id=outcome.get("invocation_id"),
    )


@router.get("/tools/{tool_id}", response_model=ToolOut)
async def read_tool(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ToolOut:
    return to_out(await get_tool(db, user, tool_id))


@router.patch("/tools/{tool_id}", response_model=ToolOut)
async def update_tool(
    tool_id: uuid.UUID,
    payload: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> ToolOut:
    tool = await get_tool(db, user, tool_id)
    _ensure_editable(tool)

    data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    secret = data.pop("secret", None)
    for key, value in data.items():
        setattr(tool, key, value)

    validate_tool_payload(
        kind=tool.kind,
        slug=tool.slug,
        config=tool.config or {},
        actions=tool.actions or [],
        input_schema=tool.input_schema or {},
    )
    if secret is not None:
        tool.secret_enc = encrypt_tool_secret(tool, secret)

    await db.flush()
    return to_out(tool)


@router.post("/tools/{tool_id}/clone", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
async def clone_tool(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> ToolOut:
    """Copy a (global) tool into the tenant so its config/secret become editable.

    The credential is **not** copied: `secret_enc` is bound to `tool:{slug}` as
    AAD, so a copy would not decrypt. The panel asks for the token again.
    """
    source = await get_tool(db, user, tool_id)

    base = f"{source.slug}.copy"[:100]
    slug = base
    suffix = 2
    while (
        await db.execute(
            select(Tool.id).where(Tool.org_id == user.org_id, Tool.slug == slug)
        )
    ).first() is not None:
        slug = f"{base}{suffix}"[:120]
        suffix += 1

    clone = Tool(
        org_id=user.org_id,
        slug=slug,
        name_fa=f"{source.name_fa} (کپی)"[:200],
        description_fa=source.description_fa,
        kind=source.kind,
        input_schema=dict(source.input_schema or {}),
        output_schema=dict(source.output_schema or {}),
        config=dict(source.config or {}),
        actions=[dict(step) for step in (source.actions or [])],
        risk_level=source.risk_level,
        approval_policy=source.approval_policy,
        category=source.category,
        is_enabled=source.is_enabled,
        created_by=user.id,
    )
    db.add(clone)
    await db.flush()
    return to_out(clone)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    tool = await get_tool(db, user, tool_id)
    _ensure_editable(tool)
    await db.delete(tool)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _mcp_out(server: McpServer) -> McpServerOut:
    data = McpServerOut.model_validate(server)
    data.has_token = bool(server.auth_enc)
    return data


async def _get_mcp_server(db: AsyncSession, user: User, server_id: uuid.UUID) -> McpServer:
    server = (
        await db.execute(
            select(McpServer).where(McpServer.id == server_id, McpServer.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if server is None:
        raise NotFoundError(code="mcp.server_not_found")
    return server


@router.get("/mcp-servers", response_model=list[McpServerOut])
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[McpServerOut]:
    rows = (
        (
            await db.execute(
                select(McpServer).where(McpServer.org_id == user.org_id).order_by(McpServer.name)
            )
        )
        .scalars()
        .all()
    )
    return [_mcp_out(row) for row in rows]


@router.post("/mcp-servers", response_model=McpServerOut, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    payload: McpServerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> McpServerOut:
    if payload.transport == "http" and not payload.url:
        raise AppError(code="mcp.missing_url", status_code=422)
    if payload.transport == "stdio" and not payload.command:
        raise AppError(code="mcp.missing_command", status_code=422)

    server = McpServer(
        org_id=user.org_id,
        name=payload.name,
        transport=payload.transport,
        url=payload.url,
        command=payload.command,
        is_enabled=payload.is_enabled,
    )
    db.add(server)
    await db.flush()

    if payload.token:
        from app.core.crypto import get_secret_box

        server.auth_enc = get_secret_box().encrypt(payload.token, aad=f"mcp:{server.id}")
        await db.flush()
    return _mcp_out(server)


@router.delete("/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    server = await _get_mcp_server(db, user, server_id)
    await db.delete(server)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mcp-servers/{server_id}/sync", response_model=McpSyncOut)
async def sync_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> McpSyncOut:
    from datetime import UTC, datetime

    server = await _get_mcp_server(db, user, server_id)
    tools = await mcp_list_tools(server)
    server.tools_cache = tools
    server.last_synced_at = datetime.now(UTC)
    await db.flush()
    return McpSyncOut(tools=tools, count=len(tools))
