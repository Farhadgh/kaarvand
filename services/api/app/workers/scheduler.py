"""Cron worker: turns due ``agent_tasks`` into runs.

Run it as its own process (never inside the API worker):

    python -m app.workers.scheduler

Guarantees:
* **single runner** across processes — a PostgreSQL advisory lock is held for
  the whole lifetime of the worker (``APP_SCHEDULER_LOCK_KEY``);
* **no double fire** — each task is claimed with an atomic UPDATE on
  ``last_run_at`` (only one worker can win), with a minimum gap of
  ``APP_SCHEDULER_MIN_GAP_SECONDS``;
* **no pile-up** — a task is skipped while one of its runs is still
  ``queued``/``running``/``waiting_approval``;
* the run is executed by the same engine as a manual run (budget, ledger,
  human approval, audit).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, update
from sqlalchemy import text as sql_text

from app.core.config import Settings, get_settings
from app.db.models import Agent, AgentTask
from app.db.session import dispose_engine, get_engine, session_scope
from app.runtime.cron import CronError, cron_matches
from app.runtime.starter import TaskRunPlan, prepare_task_run, run_to_result

log = logging.getLogger("openbot.scheduler")

ACTIVE_STATUSES = ("queued", "running", "waiting_approval")
_semaphore: asyncio.Semaphore | None = None
# the advisory lock lives as long as this connection is open; it MUST be kept
# referenced, otherwise the GC closes it and the single-runner guarantee is lost
_lock_connection: Any = None


def _sem(settings: Settings) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.scheduler_max_concurrency))
    return _semaphore


async def due_tasks(moment: datetime, settings: Settings) -> list[uuid.UUID]:
    """Read-only discovery across all organizations (bypasses tenant RLS)."""
    local = moment.astimezone(ZoneInfo(settings.scheduler_timezone))
    rows: list[uuid.UUID] = []
    async with session_scope(bypass_rls=True, settings=settings) as db:
        result = await db.execute(
            select(AgentTask.id, AgentTask.schedule_cron)
            .join(Agent, Agent.id == AgentTask.agent_id)
            .where(
                AgentTask.is_active.is_(True),
                AgentTask.trigger_type == "schedule",
                AgentTask.schedule_cron.is_not(None),
                Agent.is_active.is_(True),
                Agent.model_id.is_not(None),
            )
        )
        for task_id, expression in result.all():
            try:
                if expression and cron_matches(expression, local):
                    rows.append(task_id)
            except CronError:
                log.warning("task %s has an invalid cron %r", task_id, expression)
    return rows


async def claim_task(task_id: uuid.UUID, moment: datetime, settings: Settings) -> bool:
    """Atomically mark the task as running now; only one worker can win."""
    threshold = moment - timedelta(seconds=max(1, settings.scheduler_min_gap_seconds))
    async with session_scope(bypass_rls=True, settings=settings) as db:
        result = await db.execute(
            update(AgentTask)
            .where(
                AgentTask.id == task_id,
                or_(AgentTask.last_run_at.is_(None), AgentTask.last_run_at < threshold),
            )
            .values(last_run_at=moment)
            .returning(AgentTask.id)
        )
        return result.first() is not None


async def start_task_run(
    task_id: uuid.UUID, *, settings: Settings, mark_last_run: bool = True
) -> uuid.UUID | None:
    """Create a run for the task and execute it in the background."""
    plan = await prepare_task_run(task_id, settings=settings, mark_last_run=mark_last_run)
    if plan is None:
        log.info("task %s skipped (not runnable, busy, or unprompted)", task_id)
        return None
    if not plan.execute:
        log.info("task %s parked in waiting_approval (run %s)", task_id, plan.run_id)
        return plan.run_id
    asyncio.create_task(_execute(plan=plan))
    return plan.run_id


async def _execute(*, plan: TaskRunPlan) -> None:
    settings = get_settings()
    try:
        async with _sem(settings):
            result = await run_to_result(
                org_id=plan.org_id,
                run_id=plan.run_id,
                user_id=plan.user_id,
                settings=settings,
                input_text=plan.input_text,
            )
            log.info("run %s finished as %s", plan.run_id, result.run.status)
    except Exception:
        log.exception("run %s failed in the scheduler", plan.run_id)


async def tick(
    *, now: datetime | None = None, settings: Settings | None = None
) -> list[uuid.UUID]:
    """One scheduling pass. Returns the ids of the runs that were created."""
    cfg = settings or get_settings()
    moment = now or datetime.now(UTC)
    started: list[uuid.UUID] = []
    for task_id in await due_tasks(moment, cfg):
        if not await claim_task(task_id, moment, cfg):
            continue
        run_id = await start_task_run(task_id, settings=cfg, mark_last_run=False)
        if run_id is not None:
            started.append(run_id)
    return started


async def _hold_lock(settings: Settings) -> bool:
    """Keep one advisory lock for the worker's lifetime."""
    global _lock_connection
    engine = get_engine(settings)
    connection = await engine.connect()
    acquired = (
        await connection.execute(
            sql_text("select pg_try_advisory_lock(:key)"), {"key": settings.scheduler_lock_key}
        )
    ).scalar()
    if not acquired:
        await connection.close()
        return False
    # keep the connection referenced: the session-level lock dies with it, and a
    # garbage-collected connection would silently release the lock (two workers!)
    _lock_connection = connection
    return True


async def _release_lock() -> None:
    global _lock_connection
    if _lock_connection is None:
        return
    try:
        await _lock_connection.close()
    finally:
        _lock_connection = None


async def run_forever(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not await _hold_lock(cfg):
        log.error("another scheduler holds the lock; exiting")
        return
    log.info(
        "scheduler started (tick=%ss, tz=%s)",
        cfg.scheduler_tick_seconds,
        cfg.scheduler_timezone,
    )
    try:
        while True:
            try:
                await tick(settings=cfg)
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(max(5, cfg.scheduler_tick_seconds))
    finally:
        await _release_lock()
        await dispose_engine()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
