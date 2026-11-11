"""Usage summary and Excel export."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from openpyxl import load_workbook

from app.db.models import UsageLedger
from app.db.session import session_scope


async def _seed_ledger(org_id: uuid.UUID, agent_id: uuid.UUID | None = None) -> None:
    async with session_scope(org_id=org_id) as db:
        for index in range(3):
            db.add(
                UsageLedger(
                    org_id=org_id,
                    agent_id=agent_id,
                    tokens_in=100 + index,
                    tokens_out=20 + index,
                    cost_usd=Decimal("0.00010000"),
                    markup_percent=Decimal("0"),
                    fx_rate=Decimal("1000000"),
                    cost_irr=100,
                    billable=False,
                    created_at=datetime.now(UTC),
                )
            )


async def test_usage_summary_aggregates(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    agent = (
        await client.post("/v1/agents", headers=auth_headers, json={"name": "ایجنت مصرف"})
    ).json()
    await _seed_ledger(org_id, uuid.UUID(agent["id"]))

    response = await client.get("/v1/usage/summary", params={"days": 30}, headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["days"] == 30
    assert body["fx_rate"] > 0  # editable from the panel, so never hardcode it here
    assert body["totals"]["runs"] >= 3
    assert body["totals"]["tokens_in"] >= 303
    assert body["totals"]["cost_irr"] >= 300
    assert body["by_day"], "day buckets must not be empty"
    assert body["by_agent"][0]["label"]
    assert body["budget"]["org_spent_irr"] >= 0


async def test_usage_summary_is_tenant_scoped(
    client: Any,
    auth_headers: dict[str, str],
    admin_tokens: dict[str, Any],
    viewer_headers: dict[str, str],
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    await _seed_ledger(org_id)

    # a different organization with its own ledger must not leak into the summary
    from app.db.models import Organization

    other_org = uuid.uuid4()
    async with session_scope(bypass_rls=True) as db:
        db.add(Organization(id=other_org, name="سازمان دیگر", slug=f"other-{other_org.hex[:6]}"))
    async with session_scope(org_id=other_org) as db:
        db.add(
            UsageLedger(
                org_id=other_org,
                tokens_in=999,
                tokens_out=999,
                cost_usd=Decimal("9.00000000"),
                markup_percent=Decimal("0"),
                fx_rate=Decimal("1000000"),
                cost_irr=9_000_000_000,
                billable=False,
            )
        )

    body = (
        await client.get("/v1/usage/summary", headers=viewer_headers)
    ).json()
    assert body["totals"]["cost_irr"] < 9_000_000_000
    assert body["totals"]["tokens_in"] < 999999


async def test_export_xlsx_is_rtl_and_jalali(
    client: Any, auth_headers: dict[str, str], admin_tokens: dict[str, Any]
) -> None:
    org_id = uuid.UUID(admin_tokens["user"]["org_id"])
    agent = (
        await client.post("/v1/agents", headers=auth_headers, json={"name": "ایجنت خروجی"})
    ).json()
    await _seed_ledger(org_id, uuid.UUID(agent["id"]))

    response = await client.get("/v1/usage/export.xlsx", headers=auth_headers)
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert len(response.content) > 2000

    workbook = load_workbook(io.BytesIO(response.content))
    sheet = workbook.active
    assert sheet.sheet_view.rightToLeft is True
    assert sheet.max_row >= 2
    assert sheet.cell(row=1, column=1).value == "تاریخ (جلالی)"
    first_date = sheet.cell(row=2, column=1).value
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in str(first_date))
    assert sheet.cell(row=2, column=1).value != sheet.cell(row=1, column=1).value
