"""
APScheduler service for background task scheduling.

Manages scheduled tasks like proactive DMs, image posting, and cleanup jobs.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from src.utils.logger import logger
from src.utils.config_loader import config
from src.utils.database import get_db
from src.models.scheduled_task import ScheduledTask, TaskType, TaskStatus, TargetType


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

    # Create ScheduledTask database record
    import uuid

    with get_db() as db:
        # Calculate next run time
        next_run_time = datetime.utcnow() + timedelta(hours=interval_hours)

        # Check if pending task already exists for this job_name
        existing_task = db.query(ScheduledTask).filter(
            ScheduledTask.job_name == "random_dm_task",
            ScheduledTask.status == TaskStatus.PENDING.value
        ).first()
        if existing_task:
            db.delete(existing_task)
            db.commit()
            logger.info(f"Deleted existing pending task for random_dm_task")

        # Generate unique job_id for this execution
        unique_job_id = f"random_dm_task_{uuid.uuid4().hex[:8]}"

        # Create new task record
        task = ScheduledTask(
            job_id=unique_job_id,  # Unique per execution
            job_name="random_dm_task",  # Recurring job identifier
            task_type=TaskType.RANDOM_DM.value,
            target_type=TargetType.SYSTEM.value,
            target_id=None,
            scheduled_at=next_run_time,
            status=TaskStatus.PENDING.value,
            retry_count=0,
            meta={"interval_hours": interval_hours}
        )
        db.add(task)
        db.commit()
        logger.info(f"Created ScheduledTask record {task.job_id} for job_name=random_dm_task (next run: {next_run_time})")

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
        post_image_func: Function to call for posting image (must be callable at module level)

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

    job = sched.add_job(
        post_image_func,
        "interval",
        days=interval_days,
        id="image_post_task",
        replace_existing=True,
    )

    # Create ScheduledTask database record
    import uuid

    with get_db() as db:
        # Calculate next run time
        next_run_time = datetime.utcnow() + timedelta(days=interval_days)

        # Check if pending task already exists for this job_name
        existing_task = db.query(ScheduledTask).filter(
            ScheduledTask.job_name == "image_post_task",
            ScheduledTask.status == TaskStatus.PENDING.value
        ).first()
        if existing_task:
            db.delete(existing_task)
            db.commit()
            logger.info(f"Deleted existing pending task for image_post_task")

        # Generate unique job_id for this execution
        unique_job_id = f"image_post_task_{uuid.uuid4().hex[:8]}"

        # Create new task record
        task = ScheduledTask(
            job_id=unique_job_id,  # Unique per execution
            job_name="image_post_task",  # Recurring job identifier
            task_type=TaskType.IMAGE_POST.value,
            target_type=TargetType.CHANNEL.value,
            target_id=channel_id,
            scheduled_at=next_run_time,
            status=TaskStatus.PENDING.value,
            retry_count=0,
            meta={"interval_days": interval_days}
        )
        db.add(task)
        db.commit()
        logger.info(f"Created ScheduledTask record {task.job_id} for job_name=image_post_task (next run: {next_run_time})")

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


def update_task_after_execution(
    job_id: str,
    status: TaskStatus,
    error_message: Optional[str] = None,
    next_run_interval_hours: Optional[int] = None,
    next_run_interval_days: Optional[int] = None,
    metadata_update: Optional[dict] = None
) -> None:
    """
    Update ScheduledTask record after job execution and create next pending task.

    Args:
        job_id: The APScheduler job ID (used as job_name for grouping recurring tasks)
        status: Execution status (COMPLETED or FAILED)
        error_message: Optional error message if failed
        next_run_interval_hours: Hours until next run (for hourly tasks)
        next_run_interval_days: Days until next run (for daily tasks)
        metadata_update: Optional dict to merge into task metadata (e.g., recipient, message)
    """
    import uuid

    with get_db() as db:
        # Find and update the current pending task by job_name
        # Note: job_id parameter is actually the job_name (recurring job identifier)
        current_task = db.query(ScheduledTask).filter(
            ScheduledTask.job_name == job_id,
            ScheduledTask.status == TaskStatus.PENDING.value
        ).order_by(ScheduledTask.scheduled_at.asc()).first()

        if current_task:
            # Update current task to completed/failed
            current_task.status = status.value
            current_task.executed_at = datetime.utcnow()
            if error_message:
                current_task.error_message = error_message

            # Merge metadata_update into existing metadata
            if metadata_update:
                current_meta = current_task.meta or {}
                current_meta.update(metadata_update)
                current_task.meta = current_meta

            db.commit()
            logger.info(f"Updated ScheduledTask {current_task.id} to {status.value}")

            # Create new pending task for next run (recurring job)
            if next_run_interval_hours or next_run_interval_days:
                # Calculate next run time
                if next_run_interval_hours:
                    next_run_time = datetime.utcnow() + timedelta(hours=next_run_interval_hours)
                    meta = {"interval_hours": next_run_interval_hours}
                else:
                    next_run_time = datetime.utcnow() + timedelta(days=next_run_interval_days)
                    meta = {"interval_days": next_run_interval_days}

                # Generate unique job_id for this execution
                unique_job_id = f"{job_id}_{uuid.uuid4().hex[:8]}"

                # Create new task record
                new_task = ScheduledTask(
                    job_id=unique_job_id,  # Unique per execution
                    job_name=job_id,  # Same for all executions of this recurring job
                    task_type=current_task.task_type,
                    target_type=current_task.target_type,
                    target_id=current_task.target_id,
                    scheduled_at=next_run_time,
                    status=TaskStatus.PENDING.value,
                    retry_count=0,
                    meta=meta
                )
                db.add(new_task)
                db.commit()
                logger.info(f"Created new ScheduledTask {new_task.job_id} for job_name={job_id} (next run: {next_run_time})")
        else:
            logger.warning(f"No pending ScheduledTask found for job_name: {job_id}")


def restore_scheduled_events(scheduled_event_service) -> int:
    """
    Restore pending scheduled events on startup.

    This is called when the bot starts to reschedule any pending events
    that were scheduled before a restart.

    Args:
        scheduled_event_service: ScheduledEventService instance to use for rescheduling

    Returns:
        Number of events restored
    """
    from datetime import datetime
    from src.models.scheduled_event import ScheduledEvent

    try:
        # Get all pending events
        pending_events = scheduled_event_service.get_pending_events()

        restored_count = 0
        for event in pending_events:
            try:
                # Skip events that are in the past
                if event.scheduled_time <= datetime.utcnow():
                    logger.warning(
                        f"Skipping past event {event.id} scheduled for {event.scheduled_time}"
                    )
                    # Mark as failed
                    scheduled_event_service.repo.mark_failed(
                        event.id,
                        "Event missed due to bot restart"
                    )
                    continue

                # Remove old job if it exists
                if event.job_id:
                    try:
                        get_scheduler().remove_job(event.job_id)
                    except:
                        pass  # Job might not exist in APScheduler anymore

                # Reschedule the event (use module-level function for picklability)
                from apscheduler.triggers.date import DateTrigger
                from src.services.scheduled_event_service import execute_scheduled_event

                job_id = f"scheduled_event_{event.id}"
                get_scheduler().add_job(
                    func=execute_scheduled_event,
                    trigger=DateTrigger(run_date=event.scheduled_time),
                    args=[event.id],
                    id=job_id,
                    name=f"Event {event.id}: {event.message[:50]}",
                    misfire_grace_time=300
                )

                # Update job_id in case it changed
                event.job_id = job_id
                scheduled_event_service.repo.update(event)

                restored_count += 1
                logger.info(
                    f"Restored scheduled event {event.id} for {event.scheduled_time}"
                )

            except Exception as e:
                logger.error(f"Failed to restore event {event.id}: {e}", exc_info=True)
                continue

        logger.info(f"Restored {restored_count} scheduled events on startup")
        return restored_count

    except Exception as e:
        logger.error(f"Error restoring scheduled events: {e}", exc_info=True)
        return 0


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down")
        scheduler = None
