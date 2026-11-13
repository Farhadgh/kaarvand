"""App catalog API: list apps, install one for an agent, scan a device.

Design note: the catalog is a dictionary of *templates*. Installing copies the
template into a normal tenant `tools` row (slug `<app>.<agent8>`), so the run
engine, the risk matrix and the audit trail never learn anything new.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_agent
from app.api.v1.tools import validate_tool_payload
from app.connector.hub import hub
from app.core.deps import get_current_user, get_db, require_member
from app.core.errors import AppError, NotFoundError
from app.db.models import AgentTool, AppCatalog, Device, DeviceTool, Tool, User
from app.providers.jsonpath import fill
from app.schemas.apps import (
    AppDetailOut,
    AppInstallIn,
    AppInstallOut,
    AppOut,
    AppScanOut,
    DeviceAppGrantIn,
    DeviceAppOut,
)
from app.tools.secrets import encrypt_tool_secret

router = APIRouter(tags=["apps"])
editor = require_member


def tool_slug_for(app: AppCatalog, agent_id: uuid.UUID) -> str:
    """One tool per (app, agent): re-installing updates instead of duplicating."""
    return f"{app.slug}.{str(agent_id)[:8]}"


async def _get_app(db: AsyncSession, slug: str) -> AppCatalog:
    app = (
        await db.execute(
            select(AppCatalog).where(AppCatalog.slug == slug, AppCatalog.is_enabled.is_(True))
        )
    ).scalar_one_or_none()
    if app is None:
        raise NotFoundError(code="app.not_found")
    return app


async def _get_device(db: AsyncSession, user: User, device_id: uuid.UUID) -> Device:
    device = (
        await db.execute(
            select(Device).where(Device.id == device_id, Device.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if device is None:
        raise NotFoundError(code="device.not_found")
    return device


async def _counts(db: AsyncSession, org_id: uuid.UUID) -> dict[str, dict[str, int]]:
    """installed tools / distinct agents / detected devices per app slug."""
    tools = (
        await db.execute(select(Tool.id, Tool.config).where(Tool.org_id == org_id))
    ).all()
    by_slug: dict[str, dict[str, int]] = {}
    tool_ids: dict[uuid.UUID, str] = {}
    for tool_id, config in tools:
        slug = (config or {}).get("app_slug")
        if not slug:
            continue
        tool_ids[tool_id] = slug
        bucket = by_slug.setdefault(slug, {"tools": 0, "agents": 0, "devices": 0})
        bucket["tools"] += 1

    if tool_ids:
        pairs = (
            await db.execute(
                select(AgentTool.agent_id, AgentTool.tool_id).where(
                    AgentTool.tool_id.in_(list(tool_ids))
                )
            )
        ).all()
        agents: dict[str, set[uuid.UUID]] = {}
        for agent_id, tool_id in pairs:
            agents.setdefault(tool_ids[tool_id], set()).add(agent_id)
        for slug, ids in agents.items():
            by_slug[slug]["agents"] = len(ids)

    detected = (
        await db.execute(
            select(DeviceTool.tool_slug, func.count(DeviceTool.id))
            .join(Device, Device.id == DeviceTool.device_id)
            .where(Device.org_id == org_id)
            .group_by(DeviceTool.tool_slug)
        )
    ).all()
    for slug, count in detected:
        by_slug.setdefault(slug, {"tools": 0, "agents": 0, "devices": 0})["devices"] = int(count)
    return by_slug


def to_out(app: AppCatalog, counts: dict[str, int] | None = None) -> AppOut:
    out = AppOut.model_validate(app)
    bucket = counts or {}
    out.installed_tools = bucket.get("tools", 0)
    out.installed_agents = bucket.get("agents", 0)
    out.detected_devices = bucket.get("devices", 0)
    return out


@router.get("/apps", response_model=list[AppOut])
async def list_apps(
    category: str | None = None,
    runtime: str | None = None,
    q: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AppOut]:
    stmt = select(AppCatalog).where(AppCatalog.is_enabled.is_(True))
    if category:
        stmt = stmt.where(AppCatalog.category == category)
    if runtime:
        stmt = stmt.where(AppCatalog.runtime == runtime)
    if q:
        stmt = stmt.where(
            or_(
                AppCatalog.name_fa.ilike(f"%{q}%"),
                AppCatalog.name_en.ilike(f"%{q}%"),
                AppCatalog.slug.ilike(f"%{q}%"),
            )
        )
    rows = (
        (await db.execute(stmt.order_by(AppCatalog.sort_order, AppCatalog.slug)))
        .scalars()
        .all()
    )
    counts = await _counts(db, user.org_id)
    return [to_out(row, counts.get(row.slug)) for row in rows]


@router.get("/apps/{slug}", response_model=AppDetailOut)
async def read_app(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppDetailOut:
    app = await _get_app(db, slug)
    counts = await _counts(db, user.org_id)
    detail = AppDetailOut.model_validate(app)
    detail.installed_tools = counts.get(slug, {}).get("tools", 0)
    detail.installed_agents = counts.get(slug, {}).get("agents", 0)
    detail.detected_devices = counts.get(slug, {}).get("devices", 0)
    return detail


@router.post(
    "/apps/{slug}/install",
    response_model=AppInstallOut,
    status_code=status.HTTP_201_CREATED,
)
async def install_app(
    slug: str,
    payload: AppInstallIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AppInstallOut:
    app = await _get_app(db, slug)
    agent = await get_agent(db, user, payload.agent_id)
    warnings: list[str] = []

    # ---- wizard fields: non-secret go into the config template, one is the secret
    variables: dict[str, str] = {}
    secret_creds = []
    for cred in app.credentials or []:
        key = str(cred.get("key") or "")
        if not key:
            continue
        if cred.get("secret"):
            secret_creds.append(cred)
            continue
        value = (payload.variables or {}).get(key)
        if not value:
            if cred.get("required"):
                raise AppError(
                    code="app.missing_field", status_code=422, params={"field": key}
                )
            continue
        variables[key] = str(value)

    if secret_creds and not payload.secret:
        raise AppError(
            code="app.missing_secret",
            status_code=422,
            params={"field": str(secret_creds[0].get("key") or "token")},
        )

    # ---- desktop apps must run on a paired, online machine
    device: Device | None = None
    if payload.device_id or app.requires_device:
        if payload.device_id is None:
            raise AppError(code="app.device_required", status_code=422)
        device = await _get_device(db, user, payload.device_id)
        if hub.get(device.id) is None:
            raise AppError(
                code="app.device_offline",
                status_code=409,
                params={"device_id": str(device.id)},
            )
        detected = (
            await db.execute(
                select(DeviceTool).where(
                    DeviceTool.device_id == device.id, DeviceTool.tool_slug == app.slug
                )
            )
        ).scalar_one_or_none()
        if detected is None and not payload.force:
            raise AppError(
                code="app.not_detected",
                status_code=409,
                params={"app": app.slug, "device_id": str(device.id)},
            )
        if detected is not None and not detected.is_granted:
            warnings.append("app_not_granted")

    # ---- build the tool from the template
    config: dict[str, Any] = dict(fill(app.config_template or {}, variables))
    config["app_slug"] = app.slug
    if device is not None:
        config["device_id"] = str(device.id)
    if payload.config_overrides:
        config.update(payload.config_overrides)

    actions = [dict(step) for step in (app.actions_template or [])]
    tool_slug = tool_slug_for(app, agent.id)
    validate_tool_payload(
        kind=app.tool_kind,
        slug=tool_slug,
        config=config,
        actions=actions,
        input_schema=app.input_schema or {},
    )

    tool = (
        await db.execute(
            select(Tool).where(Tool.org_id == user.org_id, Tool.slug == tool_slug)
        )
    ).scalar_one_or_none()
    if tool is None:
        tool = Tool(org_id=user.org_id, slug=tool_slug, name_fa=payload.name_fa or app.name_fa)
        db.add(tool)
        await db.flush()
    elif payload.name_fa:
        tool.name_fa = payload.name_fa

    tool.description_fa = app.description_fa
    tool.kind = app.tool_kind
    tool.input_schema = app.input_schema or {}
    tool.config = config
    tool.actions = actions
    tool.risk_level = app.risk_level
    tool.approval_policy = app.approval_policy
    tool.category = app.category
    tool.is_enabled = True
    if payload.secret is not None:
        tool.secret_enc = encrypt_tool_secret(tool, payload.secret)
        tool.secret_label = payload.secret_label or (
            str(secret_creds[0].get("label_fa"))[:40] if secret_creds else None
        )
    await db.flush()

    binding = (
        await db.execute(
            select(AgentTool).where(
                AgentTool.agent_id == agent.id, AgentTool.tool_id == tool.id
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        db.add(
            AgentTool(
                agent_id=agent.id,
                tool_id=tool.id,
                permission_level=payload.permission_level,
                is_enabled=True,
            )
        )
    else:
        binding.permission_level = payload.permission_level
        binding.is_enabled = True
    try:
        await db.flush()
    except IntegrityError as exc:  # concurrent install of the same app
        raise AppError(code="app.install_conflict", status_code=409) from exc

    return AppInstallOut(
        tool_id=tool.id,
        slug=tool.slug,
        agent_id=agent.id,
        permission_level=payload.permission_level,
        device_id=device.id if device else None,
        warnings=warnings,
    )


@router.delete("/apps/{slug}/install", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_app(
    slug: str,
    agent_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    app = await _get_app(db, slug)
    tool = (
        await db.execute(
            select(Tool).where(
                Tool.org_id == user.org_id, Tool.slug == tool_slug_for(app, agent_id)
            )
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError(code="app.not_installed")
    for binding in (
        (await db.execute(select(AgentTool).where(AgentTool.tool_id == tool.id)))
        .scalars()
        .all()
    ):
        await db.delete(binding)
    await db.flush()
    await db.delete(tool)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _device_app_out(row: DeviceTool, app: AppCatalog | None) -> DeviceAppOut:
    capabilities = row.capabilities or {}
    return DeviceAppOut(
        app_slug=row.tool_slug,
        name_fa=app.name_fa if app else capabilities.get("name"),
        icon=app.icon if app else None,
        color=app.color if app else None,
        version=capabilities.get("version"),
        exe=capabilities.get("exe"),
        prog_id=capabilities.get("prog_id"),
        is_granted=row.is_granted,
        detected_at=capabilities.get("detected_at") or row.updated_at,
        in_catalog=app is not None,
    )


async def _catalog_map(db: AsyncSession) -> dict[str, AppCatalog]:
    rows = (await db.execute(select(AppCatalog))).scalars().all()
    return {row.slug: row for row in rows}


@router.get("/devices/{device_id}/apps", response_model=list[DeviceAppOut])
async def list_device_apps(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeviceAppOut]:
    device = await _get_device(db, user, device_id)
    rows = (
        (await db.execute(select(DeviceTool).where(DeviceTool.device_id == device.id)))
        .scalars()
        .all()
    )
    catalog = await _catalog_map(db)
    return [_device_app_out(row, catalog.get(row.tool_slug)) for row in rows]


@router.post("/devices/{device_id}/scan-apps", response_model=AppScanOut)
async def scan_device_apps(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> AppScanOut:
    """Ask the connector which catalog apps are installed on that machine."""
    device = await _get_device(db, user, device_id)
    session = hub.get(device.id)
    if session is None:
        raise AppError(
            code="app.device_offline",
            status_code=409,
            params={"device_id": str(device.id)},
        )

    catalog_rows = (await db.execute(select(AppCatalog))).scalars().all()
    reply = await hub.call(
        session=session,
        message={
            "type": "apps.scan",
            "catalog": [
                {
                    "slug": row.slug,
                    "exe": list((row.detect or {}).get("exe") or []),
                    "prog_id": (row.detect or {}).get("prog_id"),
                }
                for row in catalog_rows
            ],
        },
        timeout=25.0,
    )
    if not reply.get("ok"):
        raise AppError(
            code="app.scan_failed",
            status_code=502,
            params={"detail": str(reply.get("error") or "")[:300]},
        )

    catalog = {row.slug: row for row in catalog_rows}
    now = datetime.now(UTC)
    found = 0
    seen: set[str] = set()
    for item in reply.get("apps") or []:
        slug = _match_catalog(catalog, item)
        if slug is None or slug in seen:
            continue
        seen.add(slug)
        found += 1
        row = (
            await db.execute(
                select(DeviceTool).where(
                    DeviceTool.device_id == device.id, DeviceTool.tool_slug == slug
                )
            )
        ).scalar_one_or_none()
        capabilities = {
            "exe": item.get("exe"),
            "prog_id": item.get("prog_id"),
            "version": item.get("version"),
            "name": item.get("name"),
            "detected_at": now.isoformat(),
        }
        if row is None:
            db.add(
                DeviceTool(
                    device_id=device.id,
                    tool_slug=slug,
                    capabilities=capabilities,
                    is_granted=False,
                )
            )
        else:
            row.capabilities = capabilities
    await db.flush()

    rows = (
        (await db.execute(select(DeviceTool).where(DeviceTool.device_id == device.id)))
        .scalars()
        .all()
    )
    return AppScanOut(
        device_id=device.id,
        online=True,
        found=found,
        apps=[_device_app_out(row, catalog.get(row.tool_slug)) for row in rows],
    )


def _match_catalog(catalog: dict[str, AppCatalog], item: dict[str, Any]) -> str | None:
    """Map a reported executable/prog-id to a catalog slug."""
    exe = str(item.get("exe") or "").lower()
    prog_id = str(item.get("prog_id") or "")
    for slug, app in catalog.items():
        detect = app.detect or {}
        exes = [str(value).lower() for value in (detect.get("exe") or [])]
        progs = [str(detect.get("prog_id"))] if detect.get("prog_id") else []
        if (exe and exe in exes) or (prog_id and prog_id in progs):
            return slug
    return None


@router.patch("/devices/{device_id}/apps/{app_slug}", response_model=DeviceAppOut)
async def grant_device_app(
    device_id: uuid.UUID,
    app_slug: str,
    payload: DeviceAppGrantIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> DeviceAppOut:
    device = await _get_device(db, user, device_id)
    row = (
        await db.execute(
            select(DeviceTool).where(
                DeviceTool.device_id == device.id, DeviceTool.tool_slug == app_slug
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(code="app.not_detected")
    row.is_granted = payload.is_granted
    await db.flush()
    app = (await _catalog_map(db)).get(app_slug)
    return _device_app_out(row, app)

