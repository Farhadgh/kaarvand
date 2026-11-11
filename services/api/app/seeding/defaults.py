"""Seed helpers for catalog / prompts / billing / settings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import (
    AppSetting,
    CapabilityRule,
    FeatureFlag,
    Organization,
    Plan,
    Prompt,
    PromptVersion,
    ProviderAdapter,
    Wallet,
)
from app.seeding.catalog import CAPABILITY_RULES, PROVIDER_ADAPTERS
from app.seeding.prompts_fa import DEFAULT_PROMPTS


async def seed_catalog(db: Any) -> tuple[int, int]:
    adapters = 0
    for row in PROVIDER_ADAPTERS:
        exists = (
            await db.execute(select(ProviderAdapter).where(ProviderAdapter.kind == row["kind"]))
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                ProviderAdapter(
                    kind=row["kind"],
                    title_fa=row["title_fa"],
                    description_fa=row.get("description_fa"),
                    spec_schema=row.get("spec_schema", {}),
                )
            )
            adapters += 1

    rules = 0
    if (await db.execute(select(CapabilityRule).limit(1))).scalar_one_or_none() is None:
        for row in CAPABILITY_RULES:
            db.add(
                CapabilityRule(
                    pattern=row["pattern"],
                    flags=row["flags"],
                    priority=row["priority"],
                )
            )
            rules += 1
    return adapters, rules


async def seed_prompts(db: Any) -> int:
    created = 0
    for row in DEFAULT_PROMPTS:
        exists = (
            await db.execute(
                select(Prompt).where(
                    Prompt.org_id.is_(None),
                    Prompt.key == row["key"],
                    Prompt.locale == "fa",
                )
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        prompt = Prompt(
            org_id=None,
            key=row["key"],
            locale="fa",
            kind=row["kind"],
            title_fa=row["title_fa"],
            template=row["template"],
            variables=row.get("variables", []),
            status="published",
            current_version=1,
        )
        db.add(prompt)
        await db.flush()
        db.add(
            PromptVersion(
                prompt_id=prompt.id,
                version=1,
                template=prompt.template,
                variables=prompt.variables,
                note="نسخه‌ی اولیه (seed)",
            )
        )
        created += 1
    return created


async def seed_billing(db: Any, org: Organization) -> None:
    if (await db.execute(select(Plan).where(Plan.code == "free"))).scalar_one_or_none() is None:
        db.add(
            Plan(
                code="free",
                title_fa="پلن رایگان (فاز آزمایشی)",
                price_irr=0,
                limits={
                    "agents": 10,
                    "providers": 5,
                    "tools": 50,
                    "monthly_tokens": 1_000_000,
                    "payment_required": False,
                },
            )
        )

    wallet = (await db.execute(select(Wallet).where(Wallet.org_id == org.id))).scalar_one_or_none()
    if wallet is None:
        db.add(Wallet(org_id=org.id, balance_irr=0, currency="IRR", is_enabled=False))

    flags = (
        ("billing_enabled", False),
        ("voice_enabled", False),
        ("connector_enabled", False),
        ("mcp_enabled", True),
    )
    for key, enabled in flags:
        found = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        if found.scalar_one_or_none() is None:
            db.add(FeatureFlag(key=key, is_enabled=enabled, payload={}))


async def seed_tools(db: Any) -> int:
    """Global example tools (tenants can read them but not edit)."""
    from app.db.models import Tool
    from app.seeding.tools_seed import SEED_TOOLS

    created = 0
    for row in SEED_TOOLS:
        found = await db.execute(
            select(Tool).where(Tool.org_id.is_(None), Tool.slug == row["slug"])
        )
        if found.scalar_one_or_none() is not None:
            continue
        db.add(Tool(org_id=None, **row))
        created += 1
    return created


async def seed_apps(db: Any) -> int:
    """Global app catalog (read-only for tenants; installing copies it into `tools`).

    Existing rows are refreshed from the seed so icon/copy/template fixes reach
    installations that already exist in every tenant.
    """
    from app.db.models import AppCatalog
    from app.seeding.apps_seed import APPS

    syncable = (
        "name_fa",
        "name_en",
        "vendor",
        "description_fa",
        "icon",
        "color",
        "category",
        "runtime",
        "tool_kind",
        "input_schema",
        "config_template",
        "actions_template",
        "credentials",
        "risk_level",
        "approval_policy",
        "requires_device",
        "detect",
        "setup_fa",
        "docs_url",
        "sort_order",
    )

    created = 0
    for row in APPS:
        found = (
            await db.execute(select(AppCatalog).where(AppCatalog.slug == row["slug"]))
        ).scalar_one_or_none()
        if found is None:
            db.add(AppCatalog(**row))
            created += 1
            continue
        for key in syncable:
            if key in row:  # helpers may omit optional keys
                setattr(found, key, row[key])
    return created


async def seed_settings(db: Any) -> None:
    from app.core.config import get_settings

    defaults: dict[str, dict[str, Any]] = {
        "fx": {"usd_irr": int(get_settings().fx_usd_irr), "source": "env"},
        "product": {"free_mode": True, "locale": "fa", "calendar": "jalali"},
    }
    for key, value in defaults.items():
        found = await db.execute(select(AppSetting).where(AppSetting.key == key))
        if found.scalar_one_or_none() is None:
            db.add(AppSetting(key=key, value=value))
