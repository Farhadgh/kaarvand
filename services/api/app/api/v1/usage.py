"""Usage & cost reporting: dashboard summary and Excel export."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.fx import current_fx_rate
from app.connector.hub import hub
from app.core.deps import get_current_user, get_db
from app.core.jalali import format_jalali
from app.db.models import Agent, Device, Model, Organization, Run, UsageLedger, User
from app.runtime.budget import spent_this_month_irr
from app.schemas.usage import RunCounts, UsageBucket, UsageSummaryOut, UsageTotals

router = APIRouter(prefix="/usage", tags=["usage"])

EXCEL_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _bucket(
    key: str, label: str, runs: int, tin: int, tout: int, usd: object, irr: object
) -> UsageBucket:
    return UsageBucket(
        key=key,
        label=label,
        runs=int(runs or 0),
        tokens_in=int(tin or 0),
        tokens_out=int(tout or 0),
        cost_usd=Decimal(str(usd or 0)),
        cost_irr=int(irr or 0),
    )


async def _totals(db: AsyncSession, *window: object) -> UsageTotals:
    row = (
        await db.execute(
            select(
                func.count(UsageLedger.id),
                func.coalesce(func.sum(UsageLedger.tokens_in), 0),
                func.coalesce(func.sum(UsageLedger.tokens_out), 0),
                func.coalesce(func.sum(UsageLedger.cost_usd), 0),
                func.coalesce(func.sum(UsageLedger.cost_irr), 0),
            ).where(*window)
        )
    ).one()
    return UsageTotals(
        runs=int(row[0] or 0),
        tokens_in=int(row[1] or 0),
        tokens_out=int(row[2] or 0),
        cost_usd=Decimal(str(row[3] or 0)),
        cost_irr=int(row[4] or 0),
    )


@router.get("/summary", response_model=UsageSummaryOut)
async def usage_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UsageSummaryOut:
    since = datetime.now(UTC) - timedelta(days=days)
    org_id = user.org_id
    window = (UsageLedger.org_id == org_id, UsageLedger.created_at >= since)

    totals = await _totals(db, *window)

    day_col = func.date_trunc("day", UsageLedger.created_at)
    day_rows = (
        await db.execute(
            select(
                day_col,
                func.count(UsageLedger.id),
                func.sum(UsageLedger.tokens_in),
                func.sum(UsageLedger.tokens_out),
                func.sum(UsageLedger.cost_usd),
                func.sum(UsageLedger.cost_irr),
            )
            .where(*window)
            .group_by(day_col)
            .order_by(day_col)
        )
    ).all()
    by_day = [
        _bucket(
            row[0].date().isoformat(),
            format_jalali(row[0].date()),
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
        )
        for row in day_rows
    ]

    agent_rows = (
        await db.execute(
            select(
                Agent.id,
                Agent.name,
                func.count(UsageLedger.id),
                func.sum(UsageLedger.tokens_in),
                func.sum(UsageLedger.tokens_out),
                func.sum(UsageLedger.cost_usd),
                func.sum(UsageLedger.cost_irr),
            )
            .join(Agent, Agent.id == UsageLedger.agent_id)
            .where(*window)
            .group_by(Agent.id, Agent.name)
            .order_by(func.sum(UsageLedger.cost_irr).desc())
        )
    ).all()
    by_agent = [
        _bucket(str(row[0]), row[1], row[2], row[3], row[4], row[5], row[6]) for row in agent_rows
    ]

    model_rows = (
        await db.execute(
            select(
                Model.id,
                Model.external_id,
                func.count(UsageLedger.id),
                func.sum(UsageLedger.tokens_in),
                func.sum(UsageLedger.tokens_out),
                func.sum(UsageLedger.cost_usd),
                func.sum(UsageLedger.cost_irr),
            )
            .join(Model, Model.id == UsageLedger.model_id)
            .where(*window)
            .group_by(Model.id, Model.external_id)
            .order_by(func.sum(UsageLedger.cost_irr).desc())
        )
    ).all()
    by_model = [
        _bucket(str(row[0]), row[1], row[2], row[3], row[4], row[5], row[6]) for row in model_rows
    ]

    status_rows = (
        await db.execute(
            select(Run.status, func.count(Run.id))
            .where(Run.org_id == org_id, Run.created_at >= since)
            .group_by(Run.status)
        )
    ).all()
    statuses = {row[0]: int(row[1]) for row in status_rows}

    pending = int(
        (
            await db.execute(
                select(func.count(Run.id)).where(
                    Run.org_id == org_id, Run.status == "waiting_approval"
                )
            )
        ).scalar()
        or 0
    )

    async def _count(model: object, *where: object) -> int:
        stmt = select(func.count()).select_from(model).where(*where)
        return int((await db.execute(stmt)).scalar() or 0)

    agents_total = await _count(Agent, Agent.org_id == org_id)
    agents_active = await _count(Agent, Agent.org_id == org_id, Agent.is_active.is_(True))
    devices_total = await _count(Device, Device.org_id == org_id)

    org = await db.get(Organization, org_id)
    month_spent = await spent_this_month_irr(db, org_id=org_id)

    return UsageSummaryOut(
        days=days,
        fx_rate=await current_fx_rate(db),
        range_from=since.date().isoformat(),
        range_to=datetime.now(UTC).date().isoformat(),
        totals=totals,
        by_day=by_day,
        by_agent=by_agent,
        by_model=by_model,
        runs=RunCounts(
            running=statuses.get("running", 0),
            waiting_approval=statuses.get("waiting_approval", 0),
            failed=statuses.get("failed", 0),
            completed=statuses.get("completed", 0),
        ),
        agents_total=agents_total,
        agents_active=agents_active,
        devices_total=devices_total,
        devices_online=len(hub.online_devices(org_id)),
        pending_approvals=pending,
        budget={
            "org_monthly_irr": org.monthly_budget_irr if org else None,
            "org_spent_irr": month_spent,
        },
    )


@router.get("/export.xlsx")
async def export_usage_xlsx(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Excel export: RTL sheet, Jalali dates, Persian headers, real numbers."""
    from zoneinfo import ZoneInfo

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                UsageLedger.created_at,
                Agent.name,
                Model.external_id,
                UsageLedger.tokens_in,
                UsageLedger.tokens_out,
                UsageLedger.cost_usd,
                UsageLedger.cost_irr,
                UsageLedger.billable,
            )
            .outerjoin(Agent, Agent.id == UsageLedger.agent_id)
            .outerjoin(Model, Model.id == UsageLedger.model_id)
            .where(UsageLedger.org_id == user.org_id, UsageLedger.created_at >= since)
            .order_by(UsageLedger.created_at.desc())
            .limit(20000)
        )
    ).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "مصرف"
    sheet.sheet_view.rightToLeft = True

    headers = [
        "تاریخ (جلالی)",
        "ساعت",
        "ایجنت",
        "مدل",
        "توکن ورودی",
        "توکن خروجی",
        "هزینه (دلار)",
        "هزینه (ریال)",
        "قابل صورت‌حساب",
    ]
    sheet.append(headers)
    header_fill = PatternFill("solid", start_color="FFE8EEF7")
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    tehran = ZoneInfo("Asia/Tehran")
    for row in rows:
        at = row[0].astimezone(tehran)
        sheet.append(
            [
                format_jalali(at.date()),
                at.strftime("%H:%M"),
                row[1] or "—",
                row[2] or "—",
                int(row[3] or 0),
                int(row[4] or 0),
                float(row[5] or 0),
                int(row[6] or 0),
                "بله" if row[7] else "خیر",
            ]
        )

    for index, width in enumerate((14, 8, 26, 30, 14, 14, 16, 18, 16), start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row_index in range(2, sheet.max_row + 1):
        sheet.cell(row=row_index, column=5).number_format = "#,##0"
        sheet.cell(row=row_index, column=6).number_format = "#,##0"
        sheet.cell(row=row_index, column=7).number_format = "#,##0.00000000"
        sheet.cell(row=row_index, column=8).number_format = "#,##0"
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"kaarvand-usage-{datetime.now(tehran).date().isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type=EXCEL_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
