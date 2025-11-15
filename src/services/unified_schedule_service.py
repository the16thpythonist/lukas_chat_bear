"""
Unified Schedule Service

Provides a unified view of all scheduled activities across both
scheduled_events and scheduled_tasks tables.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from src.models.scheduled_event import ScheduledEvent
from src.models.scheduled_task import ScheduledTask, TaskType
from src.repositories.scheduled_event_repo import ScheduledEventRepository
from src.repositories.scheduled_task_repo import ScheduledTaskRepository
from src.utils.logger import logger


class UnifiedScheduleService:
    """Service for unified view of all scheduled activities."""

    def __init__(self, db_session: Session, scheduler: BackgroundScheduler):
        """
        Initialize service.

        Args:
            db_session: Database session
            scheduler: APScheduler instance
        """
        self.db_session = db_session
        self.scheduler = scheduler
        self.event_repo = ScheduledEventRepository(db_session)
        self.task_repo = ScheduledTaskRepository(db_session)

    def get_all_scheduled_events(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all scheduled events from both sources, normalized and merged.

        Args:
            status: Optional status filter (pending, completed, failed, cancelled)
            limit: Maximum number of results

        Returns:
            List of normalized event dictionaries
        """
        unified_events = []

        # 1. Get scheduled channel messages (scheduled_events table)
        channel_messages = self.event_repo.get_all(status=status)
        for event in channel_messages:
            unified_events.append(self._normalize_scheduled_event(event))

        # 2. Get recurring system tasks (scheduled_tasks table)
        # Only get pending recurring tasks (show next occurrence only)
        if status is None or status == 'pending':
            recurring_tasks = self.task_repo.get_pending_recurring_tasks()
            for task in recurring_tasks:
                unified_events.append(self._normalize_scheduled_task(task))

        # If status filter is for completed/failed/cancelled, also get from scheduled_tasks
        if status in ['completed', 'failed', 'cancelled']:
            historical_tasks = self.task_repo.get_all(
                status=status,
                task_type=None  # Get all types
            )
            for task in historical_tasks:
                # Only include recurring tasks (have job_name)
                if task.job_name in ['random_dm_task', 'image_post_task']:
                    unified_events.append(self._normalize_scheduled_task(task))

        # Sort by scheduled time (ascending - soonest first)
        unified_events.sort(key=lambda x: x['scheduled_time'])

        # Apply limit
        if limit:
            unified_events = unified_events[:limit]

        logger.info(
            f"Unified schedule: {len(unified_events)} events "
            f"(status={status or 'all'})"
        )

        return unified_events

    def cancel_recurring_task(self, job_name: str) -> Dict[str, Any]:
        """
        Cancel a recurring task (random_dm_task or image_post_task).

        This will:
        1. Remove the APScheduler job (stops future executions)
        2. Mark pending ScheduledTask records as cancelled

        Args:
            job_name: Job name (random_dm_task or image_post_task)

        Returns:
            Dict with success status and message
        """
        try:
            # Validate job_name
            if job_name not in ['random_dm_task', 'image_post_task']:
                return {
                    'success': False,
                    'error': f'Invalid job_name: {job_name}'
                }

            # Remove APScheduler job
            try:
                job = self.scheduler.get_job(job_name)
                if job:
                    self.scheduler.remove_job(job_name)
                    logger.info(f"Removed APScheduler job: {job_name}")
                else:
                    logger.warning(f"APScheduler job not found: {job_name}")
            except Exception as e:
                logger.error(f"Error removing APScheduler job {job_name}: {e}")
                # Continue anyway to mark DB records as cancelled

            # Mark pending tasks as cancelled
            cancelled_count = self.task_repo.mark_cancelled_by_job_name(job_name)

            task_type = "Random DM" if job_name == "random_dm_task" else "Image Post"

            return {
                'success': True,
                'message': f'{task_type} recurring task cancelled. {cancelled_count} pending task(s) marked as cancelled.',
                'job_name': job_name,
                'cancelled_count': cancelled_count
            }

        except Exception as e:
            logger.error(f"Error cancelling recurring task {job_name}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _normalize_scheduled_event(self, event: ScheduledEvent) -> Dict[str, Any]:
        """
        Normalize a ScheduledEvent to unified format.

        Args:
            event: ScheduledEvent model instance

        Returns:
            Normalized dictionary
        """
        return {
            'id': f'event_{event.id}',
            'source': 'scheduled_events',
            'type': 'channel_message',
            'type_display': 'Channel Message',
            'scheduled_time': event.scheduled_time.isoformat() if event.scheduled_time else None,
            'status': event.status,
            'target': event.target_channel_name or event.target_channel_id,
            'message': event.message,
            'is_recurring': False,
            'recurrence_info': None,
            'created_by': event.created_by_user_name or 'Unknown',
            'can_edit': event.status == 'pending',
            'can_cancel': event.status == 'pending',
            'job_name': None,
            'executed_at': event.executed_at.isoformat() if event.executed_at else None,
            'error_message': event.error_message,
            # For edit/cancel operations
            '_raw_id': event.id,
            '_source_type': 'event'
        }

    def _normalize_scheduled_task(self, task: ScheduledTask) -> Dict[str, Any]:
        """
        Normalize a ScheduledTask to unified format.

        Args:
            task: ScheduledTask model instance

        Returns:
            Normalized dictionary
        """
        # Determine type and display name
        if task.task_type == TaskType.RANDOM_DM.value:
            type_key = 'random_dm'
            type_display = 'Random DM'
            target = 'Random team member'
            message = 'Send proactive DM to a team member'
        elif task.task_type == TaskType.IMAGE_POST.value:
            type_key = 'image_post'
            type_display = 'Image Post'
            # Get target channel from metadata
            target_channel = task.meta.get('target_channel', '#random') if task.meta else '#random'
            target = target_channel
            message = f'Post AI-generated image to {target_channel}'
        else:
            type_key = task.task_type
            type_display = task.task_type.replace('_', ' ').title()
            target = task.target_id or 'System'
            message = f'Execute {type_display}'

        # Determine recurrence info
        is_recurring = task.job_name is not None
        recurrence_info = None
        if is_recurring and task.meta:
            if 'interval_hours' in task.meta:
                hours = task.meta['interval_hours']
                recurrence_info = f'Every {hours} hour{"s" if hours != 1 else ""}'
            elif 'interval_days' in task.meta:
                days = task.meta['interval_days']
                recurrence_info = f'Every {days} day{"s" if days != 1 else ""}'

        return {
            'id': f'task_{task.id}',
            'source': 'scheduled_tasks',
            'type': type_key,
            'type_display': type_display,
            'scheduled_time': task.scheduled_at.isoformat() if task.scheduled_at else None,
            'status': task.status,
            'target': target,
            'message': message,
            'is_recurring': is_recurring,
            'recurrence_info': recurrence_info,
            'created_by': 'System',
            'can_edit': False,  # System tasks cannot be edited
            'can_cancel': task.status == 'pending' and is_recurring,  # Can cancel recurring tasks
            'job_name': task.job_name,
            'executed_at': task.executed_at.isoformat() if task.executed_at else None,
            'error_message': task.error_message,
            # For cancel operations
            '_raw_id': task.id,
            '_source_type': 'task'
        }
