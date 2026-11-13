"""Idempotent seed: default organization, admin user, catalogs and prompts.

Run:  python -m app.seeding
Env:  OPENBOT_ADMIN_EMAIL / OPENBOT_ADMIN_PASSWORD override the dev defaults.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select

from app.billing.wallet import get_or_create_wallet
from app.core.security import hash_password
from app.db.models import Agent, Organization, User
from app.db.session import session_scope
from app.seeding.defaults import (
    seed_apps,
    seed_billing,
    seed_catalog,
    seed_prompts,
    seed_settings,
    seed_tools,
)

ORG_SLUG = "default"
ORG_NAME = "سازمان نمونه"
ADMIN_EMAIL = os.getenv("OPENBOT_ADMIN_EMAIL", "admin@openbot.local").lower()
ADMIN_PASSWORD = os.getenv("OPENBOT_ADMIN_PASSWORD", "admin12345")
ADMIN_NAME = "مدیر سیستم"


async def _org(db: Any) -> Organization:
    org = (
        await db.execute(select(Organization).where(Organization.slug == ORG_SLUG))
    ).scalar_one_or_none()
    if org is not None:
        return org
    org = Organization(
        name=ORG_NAME,
        slug=ORG_SLUG,
        timezone="Asia/Tehran",
        calendar="jalali",
        currency="IRR",
        digits="fa",
    )
    db.add(org)
    await db.flush()
    return org


async def _admin(db: Any, org: Organization) -> User:
    user = (
        await db.execute(select(User).where(User.org_id == org.id, User.email == ADMIN_EMAIL))
    ).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        org_id=org.id,
        email=ADMIN_EMAIL,
        full_name=ADMIN_NAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        role="admin",
        locale="fa",
        digits_pref="fa",
        is_phone_verified=False,
    )
    db.add(user)
    await db.flush()
    await get_or_create_wallet(db, org_id=org.id, user_id=user.id)
    return user


async def _agent(db: Any, org: Organization, user: User) -> Agent:
    agent = (
        await db.execute(select(Agent).where(Agent.org_id == org.id, Agent.name == "دستیار عمومی"))
    ).scalar_one_or_none()
    if agent is not None:
        return agent
    agent = Agent(
        org_id=org.id,
        name="دستیار عمومی",
        role="assistant",
        system_prompt_key="agent.system.default",
        memory_mode="short",
        created_by=user.id,
    )
    db.add(agent)
    await db.flush()
    return agent


async def run_seed() -> dict[str, Any]:
    async with session_scope(bypass_rls=True) as db:
        org = await _org(db)
        user = await _admin(db, org)
        adapters, rules = await seed_catalog(db)
        prompts = await seed_prompts(db)
        tools = await seed_tools(db)
        apps = await seed_apps(db)
        await seed_billing(db, org)
        await seed_settings(db)
        agent = await _agent(db, org, user)

    return {
        "org_slug": ORG_SLUG,
        "org_id": str(org.id),
        "admin_email": ADMIN_EMAIL,
        "adapters_created": adapters,
        "capability_rules_created": rules,
        "prompts_created": prompts,
        "tools_created": tools,
        "apps_created": apps,
        "agent": agent.name,
    }
