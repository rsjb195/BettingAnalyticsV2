"""
APScheduler-based job scheduler for recurring data operations.

Schedules:
  - Daily refresh at 3:00 AM UK time
  - Saturday slate preparation at 9:00 AM UK time on Saturdays
  - Weekly player data sync at 2:00 AM UK time on Mondays

All times are in Europe/London timezone.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("ingestion.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _job_daily_refresh() -> None:
    """Wrapper for the daily refresh job."""
    logger.info("Scheduler: Starting daily refresh job at %s", datetime.utcnow().isoformat())
    try:
        from backend.scripts.daily_refresh import run_daily_refresh
        await run_daily_refresh()
        logger.info("Scheduler: Daily refresh job completed successfully.")
    except Exception as e:
        logger.exception("Scheduler: Daily refresh job failed: %s", e)


async def _job_saturday_slate() -> None:
    """Wrapper for the Saturday slate preparation job."""
    logger.info("Scheduler: Starting Saturday slate job at %s", datetime.utcnow().isoformat())
    try:
        from backend.scripts.daily_refresh import run_saturday_slate
        await run_saturday_slate()
        logger.info("Scheduler: Saturday slate job completed successfully.")
    except Exception as e:
        logger.exception("Scheduler: Saturday slate job failed: %s", e)


def init_scheduler() -> AsyncIOScheduler:
    """
    Initialise and configure the APScheduler instance.

    Call this from the FastAPI lifespan event to start scheduled jobs.

    Returns:
        Configured AsyncIOScheduler instance.
    """
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Europe/London")

    # Daily refresh — 3:00 AM UK time, every day
    _scheduler.add_job(
        _job_daily_refresh,
        trigger=CronTrigger(hour=3, minute=0, timezone="Europe/London"),
        id="daily_refresh",
        name="Daily data refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Saturday slate — 9:00 AM UK time, Saturdays only
    _scheduler.add_job(
        _job_saturday_slate,
        trigger=CronTrigger(day_of_week="sat", hour=9, minute=0, timezone="Europe/London"),
        id="saturday_slate",
        name="Saturday slate preparation",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("Scheduler initialised with %d jobs.", len(_scheduler.get_jobs()))
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler. Idempotent — safe to call multiple times."""
    global _scheduler
    if _scheduler is None:
        init_scheduler()
    if not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started.")


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped.")


def get_scheduler_status() -> dict:
    """Return current scheduler status and job info."""
    if _scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
    }
