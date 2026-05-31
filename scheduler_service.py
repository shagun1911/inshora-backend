"""In-process blog scheduler — runs inside the Flask/gunicorn web service (no separate cron)."""

from __future__ import annotations

import atexit
import fcntl
import logging
import os
from datetime import datetime
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_lock_file = None
_schedule_info: dict = {}


def _scheduler_enabled() -> bool:
    return os.getenv("BLOG_SCHEDULER_ENABLED", "true").lower() not in ("0", "false", "no")


def get_scheduler_status() -> dict:
    """Return scheduler state for health/debug endpoints."""
    status = {
        "enabled": _scheduler_enabled(),
        "running": _scheduler is not None and _scheduler.running,
        "timezone": os.getenv("BLOG_SCHEDULER_TIMEZONE", "America/Chicago"),
        "schedule": _schedule_info,
    }
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("daily_blog_post")
        if job and job.next_run_time:
            status["next_run"] = job.next_run_time.isoformat()
    return status


def shutdown_blog_scheduler() -> None:
    global _scheduler, _lock_file
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("Blog scheduler shut down")
        except Exception as exc:
            logger.warning("Blog scheduler shutdown error: %s", exc)
        _scheduler = None
    if _lock_file is not None:
        try:
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()
        except Exception:
            pass
        _lock_file = None


def init_blog_scheduler() -> None:
    """Start daily blog job in this process. Only one gunicorn worker acquires the lock."""
    global _scheduler, _lock_file, _schedule_info

    if not _scheduler_enabled():
        logger.info("Blog scheduler disabled (BLOG_SCHEDULER_ENABLED=false)")
        return

    if _scheduler is not None and _scheduler.running:
        return

    lock_path = Path(__file__).parent / "scheduler_process.lock"
    try:
        _lock_file = open(lock_path, "w")
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.info("Blog scheduler already active in another worker — skipping")
        return
    except OSError as exc:
        logger.warning("Could not acquire scheduler lock: %s", exc)
        return

    from blog_scheduler import generate_and_publish_blog

    tz_name = os.getenv("BLOG_SCHEDULER_TIMEZONE", "America/Chicago")
    tz = pytz.timezone(tz_name)
    _scheduler = BackgroundScheduler(timezone=tz)

    interval_hours = os.getenv("BLOG_SCHEDULER_INTERVAL_HOURS", "").strip()
    if interval_hours:
        hours = float(interval_hours)
        _scheduler.add_job(
            generate_and_publish_blog,
            trigger=IntervalTrigger(hours=hours, timezone=tz),
            id="daily_blog_post",
            name="Daily Blog Post Generation",
            replace_existing=True,
        )
        _schedule_info = {"mode": "interval", "hours": hours, "timezone": tz_name}
        logger.info("Blog scheduler: every %.1f hours (%s)", hours, tz_name)
    else:
        hour = int(os.getenv("BLOG_SCHEDULER_HOUR", "6"))
        minute = int(os.getenv("BLOG_SCHEDULER_MINUTE", "0"))
        _scheduler.add_job(
            generate_and_publish_blog,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id="daily_blog_post",
            name="Daily Blog Post Generation",
            replace_existing=True,
        )
        _schedule_info = {
            "mode": "daily",
            "hour": hour,
            "minute": minute,
            "timezone": tz_name,
        }
        logger.info("Blog scheduler: daily at %02d:%02d %s", hour, minute, tz_name)

    _scheduler.start()
    atexit.register(shutdown_blog_scheduler)

    job = _scheduler.get_job("daily_blog_post")
    if job and job.next_run_time:
        logger.info("Next blog run: %s", job.next_run_time.isoformat())
