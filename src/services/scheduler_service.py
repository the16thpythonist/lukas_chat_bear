"""
APScheduler service for background task scheduling.

Manages scheduled tasks like proactive DMs, image posting, and cleanup jobs.
"""

import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from src.utils.logger import logger
from src.utils.config_loader import config


# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None


def init_scheduler(db_path: Optional[str] = None) -> BackgroundScheduler:
    """
    Initialize and configure APScheduler.

    Args:
        db_path: Optional database path (for testing). If not provided, uses DATABASE_URL env var.

    Returns:
        Configured BackgroundScheduler instance
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler

    # Database URL for job store
    if db_path:
        database_url = f"sqlite:///{db_path}"
    else:
        database_url = os.getenv("DATABASE_URL", "sqlite:///data/lukas.db")

    # Configure job stores
    jobstores = {
        "default": SQLAlchemyJobStore(url=database_url, tablename="apscheduler_jobs")
    }

    # Configure executors
    executors = {
        "default": ThreadPoolExecutor(max_workers=5)
    }

    # Job defaults
    job_defaults = {
        "coalesce": True,  # Combine missed runs into one
        "max_instances": 1,  # Only one instance of each job at a time
        "misfire_grace_time": 300,  # 5 minutes grace period for missed jobs
    }

    # Create scheduler
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone="UTC",
    )

    # Start scheduler
    scheduler.start()
    logger.info("APScheduler initialized and started")

    return scheduler


def get_scheduler() -> BackgroundScheduler:
    """
    Get the scheduler instance.

    Returns:
        BackgroundScheduler instance

    Raises:
        RuntimeError: If scheduler not initialized
    """
    if scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    return scheduler


def schedule_random_dm_task(interval_hours: int = 24, send_random_dm_func=None):
    """
    Schedule recurring random DM task.

    Args:
        interval_hours: Hours between random DMs
        send_random_dm_func: Function to call for sending random DM

    Returns:
        Job object if scheduled, None if not

    Raises:
        TypeError: If send_random_dm_func is None
    """
    if send_random_dm_func is None:
        logger.warning("No send_random_dm function provided")
        raise TypeError("send_random_dm_func cannot be None")

    sched = get_scheduler()
    job = sched.add_job(
        send_random_dm_func,
        "interval",
        hours=interval_hours,
        id="random_dm_task",
        replace_existing=True,
    )

    logger.info(f"Random DM task scheduled (interval: {interval_hours}h)")
    return job


def schedule_image_post_task(
    interval_days: int = 7,
    channel_id: str = None,
    post_image_func=None
) -> Optional[any]:
    """
    Schedule recurring image posting task.

    Args:
        interval_days: Days between image posts
        channel_id: Slack channel ID to post to (e.g., "C12345678" for #random)
        post_image_func: Async function to call for posting image

    Returns:
        Job object if scheduled, None if not

    Raises:
        TypeError: If required parameters are None
    """
    if post_image_func is None:
        logger.warning("No post_image function provided")
        raise TypeError("post_image_func cannot be None")

    if channel_id is None:
        logger.warning("No channel_id provided for image posting")
        raise TypeError("channel_id cannot be None")

    sched = get_scheduler()

    # Create wrapper function for async call
    def sync_wrapper():
        import asyncio
        asyncio.run(post_image_func(channel_id))

    job = sched.add_job(
        sync_wrapper,
        "interval",
        days=interval_days,
        id="image_post_task",
        replace_existing=True,
    )

    logger.info(f"Image post task scheduled (interval: {interval_days}d, channel: {channel_id})")
    return job


def schedule_cleanup_task(cron_expression: str = "0 2 * * *") -> None:
    """
    Schedule daily cleanup task.

    Args:
        cron_expression: Cron expression (default: 2:00 AM daily)
    """
    # TODO: Implement once cleanup service is ready
    # from src.services.cleanup_service import run_cleanup

    # sched = get_scheduler()
    # sched.add_job(
    #     run_cleanup,
    #     "cron",
    #     hour=2,
    #     minute=0,
    #     id="cleanup_task",
    #     replace_existing=True,
    # )

    logger.info(f"Cleanup task will be scheduled (cron: {cron_expression})")


def get_scheduled_task_info(job_id: str) -> Optional[dict]:
    """
    Get information about a scheduled task.

    Args:
        job_id: The ID of the job to query

    Returns:
        Dict with job information or None if job doesn't exist
    """
    try:
        sched = get_scheduler()
        job = sched.get_job(job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
    except Exception as e:
        logger.error(f"Error getting job info for {job_id}: {e}")
        return None


def remove_scheduled_task(job_id: str) -> bool:
    """
    Remove a scheduled task.

    Args:
        job_id: The ID of the job to remove

    Returns:
        True if removed, False if job didn't exist
    """
    try:
        sched = get_scheduler()
        job = sched.get_job(job_id)
        if job is None:
            logger.warning(f"Job {job_id} does not exist")
            return False
        sched.remove_job(job_id)
        logger.info(f"Removed scheduled task: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing job {job_id}: {e}")
        return False


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down")
        scheduler = None
