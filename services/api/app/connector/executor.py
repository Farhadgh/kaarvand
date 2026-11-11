"""Execute a connector tool (action script) on a paired device."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.hub import hub
from app.core.errors import AppError
from app.db.models import Device, Tool
from app.providers.jsonpath import fill


def build_steps(
    actions: list[dict[str, Any]],
    args: dict[str, Any],
    *,
    run_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Substitute ``{{input.x}}`` / ``{{run_id}}`` in the action script."""
    variables: dict[str, Any] = {
        "run_id": str(run_id) if run_id else "",
        "org_id": str(org_id) if org_id else "",
    }
    for key, value in args.items():
        variables[f"input.{key}"] = value
    return [fill(step, variables) for step in actions]


async def execute_connector_tool(
    db: AsyncSession,
    *,
    tool: Tool,
    args: dict[str, Any],
    org_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    config = tool.config or {}
    raw_device = config.get("device_id")
    device_id = uuid.UUID(str(raw_device)) if raw_device else None

    session = hub.pick(org_id, device_id)
    if session is None:
        raise AppError(
            code="tool.device_offline",
            status_code=409,
            params={"device_id": str(device_id) if device_id else None},
        )

    steps = build_steps(tool.actions or [], args, run_id=run_id, org_id=org_id)
    if not steps:
        raise AppError(
            code="tool.invalid_actions", status_code=422, params={"reason": "no_actions"}
        )

    device = await db.get(Device, session.device_id)
    allow_paths = list(device.allowed_paths or []) if device else []

    reply = await hub.call(
        session=session,
        message={
            "type": "script.run",
            "tool": tool.slug,
            "steps": steps,
            "allow_paths": allow_paths,
            "timeout": timeout,
        },
        timeout=timeout,
    )

    if not reply.get("ok", False):
        raise AppError(
            code="tool.device_error",
            status_code=502,
            params={
                "device_id": str(session.device_id),
                "detail": str(reply.get("error") or "")[:300],
                "step": reply.get("step"),
            },
        )

    return {
        "device_id": str(session.device_id),
        "steps": len(steps),
        "output": reply.get("output"),
        "artifacts": reply.get("artifacts") or [],
    }
