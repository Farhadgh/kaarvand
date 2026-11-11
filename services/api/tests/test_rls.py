"""Row level security: tenants must never see each other's rows."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import Agent, Organization
from app.db.session import session_scope


async def test_rls_isolates_tenants() -> None:
    suffix = uuid.uuid4().hex[:8]
    name_a = f"agent-a-{suffix}"
    name_b = f"agent-b-{suffix}"

    async with session_scope(bypass_rls=True) as db:
        org_a = Organization(name="سازمان الف", slug=f"a-{suffix}")
        org_b = Organization(name="سازمان ب", slug=f"b-{suffix}")
        db.add_all([org_a, org_b])
        await db.flush()
        db.add_all(
            [
                Agent(org_id=org_a.id, name=name_a),
                Agent(org_id=org_b.id, name=name_b),
            ]
        )
        org_a_id, org_b_id = org_a.id, org_b.id

    async with session_scope(org_id=org_a_id) as db:
        visible = (
            (await db.execute(select(Agent.name).where(Agent.name.like(f"agent-%-{suffix}"))))
            .scalars()
            .all()
        )
    assert visible == [name_a]

    async with session_scope(org_id=org_b_id) as db:
        visible = (
            (await db.execute(select(Agent.name).where(Agent.name.like(f"agent-%-{suffix}"))))
            .scalars()
            .all()
        )
    assert visible == [name_b]


async def test_without_tenant_context_nothing_is_visible() -> None:
    suffix = uuid.uuid4().hex[:8]
    name = f"agent-orphan-{suffix}"

    async with session_scope(bypass_rls=True) as db:
        org = Organization(name="سازمان ج", slug=f"c-{suffix}")
        db.add(org)
        await db.flush()
        db.add(Agent(org_id=org.id, name=name))

    async with session_scope() as db:
        visible = (await db.execute(select(Agent.name).where(Agent.name == name))).scalars().all()
    assert visible == []
