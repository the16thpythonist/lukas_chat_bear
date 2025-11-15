"""
Scheduled Task Repository

Data access layer for scheduled_tasks table.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.scheduled_task import ScheduledTask, TaskStatus, TaskType
from src.utils.logger import logger


class ScheduledTaskRepository:
    """Repository for ScheduledTask database operations."""

    def __init__(self, db_session: Session):
        """
        Initialize repository.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def get_by_id(self, task_id: str) -> Optional[ScheduledTask]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            ScheduledTask or None if not found
        """
        return self.db_session.query(ScheduledTask).filter(
            ScheduledTask.id == task_id
        ).first()

    def get_by_job_name(self, job_name: str, status: Optional[str] = None) -> List[ScheduledTask]:
        """
        Get tasks by job name (for recurring tasks).

        Args:
            job_name: Job name (e.g., "random_dm_task", "image_post_task")
            status: Optional status filter

        Returns:
            List of tasks
        """
        query = self.db_session.query(ScheduledTask).filter(
            ScheduledTask.job_name == job_name
        )

        if status:
            query = query.filter(ScheduledTask.status == status)

        return query.order_by(ScheduledTask.scheduled_at.desc()).all()

    def get_pending(self, task_type: Optional[str] = None) -> List[ScheduledTask]:
        """
        Get all pending tasks.

        Args:
            task_type: Optional task type filter (random_dm, image_post, etc.)

        Returns:
            List of pending tasks
        """
        query = self.db_session.query(ScheduledTask).filter(
            ScheduledTask.status == TaskStatus.PENDING.value
        )

        if task_type:
            query = query.filter(ScheduledTask.task_type == task_type)

        return query.order_by(ScheduledTask.scheduled_at.asc()).all()

    def get_pending_recurring_tasks(self) -> List[ScheduledTask]:
        """
        Get pending recurring tasks (random DM and image posts).

        Returns:
            List of pending recurring tasks (one per job_name)
        """
        # Get pending tasks with job_name (recurring tasks only)
        return self.db_session.query(ScheduledTask).filter(
            and_(
                ScheduledTask.status == TaskStatus.PENDING.value,
                ScheduledTask.job_name.isnot(None),
                or_(
                    ScheduledTask.task_type == TaskType.RANDOM_DM.value,
                    ScheduledTask.task_type == TaskType.IMAGE_POST.value
                )
            )
        ).order_by(ScheduledTask.scheduled_at.asc()).all()

    def get_all(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ScheduledTask]:
        """
        Get all tasks with optional filtering.

        Args:
            status: Optional status filter
            task_type: Optional task type filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of tasks
        """
        query = self.db_session.query(ScheduledTask)

        if status:
            query = query.filter(ScheduledTask.status == status)

        if task_type:
            query = query.filter(ScheduledTask.task_type == task_type)

        query = query.order_by(ScheduledTask.scheduled_at.desc())

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def mark_cancelled(self, task_id: str) -> bool:
        """
        Mark a task as cancelled.

        Args:
            task_id: Task ID

        Returns:
            True if successful, False if not found
        """
        task = self.get_by_id(task_id)
        if not task:
            return False

        task.status = TaskStatus.CANCELLED.value
        self.db_session.commit()
        logger.info(f"Marked task {task_id} as cancelled")
        return True

    def mark_cancelled_by_job_name(self, job_name: str) -> int:
        """
        Mark all pending tasks with given job_name as cancelled.

        Used when canceling recurring tasks.

        Args:
            job_name: Job name (e.g., "random_dm_task")

        Returns:
            Number of tasks marked as cancelled
        """
        tasks = self.get_by_job_name(job_name, status=TaskStatus.PENDING.value)

        count = 0
        for task in tasks:
            task.status = TaskStatus.CANCELLED.value
            count += 1

        if count > 0:
            self.db_session.commit()
            logger.info(f"Marked {count} pending tasks for job_name={job_name} as cancelled")

        return count
