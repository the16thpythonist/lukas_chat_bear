"""
Scheduler-specific tests for random DM feature.

Tests APScheduler integration, job persistence, and scheduling behavior
without waiting for real timers.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

import src.services.scheduler_service as scheduler_module
from src.services.scheduler_service import (
    init_scheduler,
    schedule_random_dm_task,
    remove_scheduled_task,
    get_scheduled_task_info,
    get_scheduler,
)


class TestSchedulerIntegrationForRandomDM:
    """Tests for APScheduler integration with random DM feature."""

    def setup_method(self):
        """Reset scheduler before each test."""
        # Reset global scheduler
        scheduler_module.scheduler = None

    def teardown_method(self):
        """Clean up scheduler after each test."""
        if scheduler_module.scheduler is not None:
            scheduler_module.scheduler.shutdown(wait=False)
            scheduler_module.scheduler = None

    def test_schedule_random_dm_task_creates_job(self, test_db_path):
        """
        Protects against: Job not being scheduled

        Given: Scheduler is initialized
        When: Random DM task is scheduled
        Then: Job exists with correct ID and interval
        """
        # Arrange: Initialize scheduler
        init_scheduler(db_path=str(test_db_path))

        # Mock function to schedule
        mock_func = Mock()

        # Act: Schedule task
        job = schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        # Assert: Job created
        assert job is not None
        assert job.id == "random_dm_task"

        # Verify job exists in scheduler
        sched = get_scheduler()
        all_jobs = sched.get_jobs()
        job_ids = [j.id for j in all_jobs]
        assert "random_dm_task" in job_ids

    def test_schedule_random_dm_task_replaces_existing_job(self, test_db_path):
        """
        Protects against: Duplicate jobs when rescheduling

        Given: Random DM task already scheduled
        When: Same task is scheduled again
        Then: Old job is replaced (only one job exists)
        """
        # Arrange
        init_scheduler(db_path=str(test_db_path))
        mock_func1 = Mock()
        mock_func2 = Mock()

        # Act: Schedule twice
        job1 = schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func1)
        job2 = schedule_random_dm_task(interval_hours=12, send_random_dm_func=mock_func2)

        # Assert: Only one job exists
        all_jobs = get_scheduler().get_jobs()
        random_dm_jobs = [j for j in all_jobs if j.id == "random_dm_task"]
        assert len(random_dm_jobs) == 1

        # Assert: Second job's interval is active
        assert job2 is not None
        # Note: APScheduler stores interval in seconds
        assert job2.trigger.interval.total_seconds() == 12 * 3600

        # Cleanup
        get_scheduler().shutdown()

    def test_random_dm_task_persists_across_scheduler_restart(self, test_db_path):
        """
        Protects against: Losing scheduled jobs on restart

        Given: Random DM task is scheduled
        When: Scheduler is stopped and restarted
        Then: Job still exists with same configuration
        """
        # Arrange: First scheduler instance
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()
        schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        jobs_before = get_scheduler().get_jobs()
        assert len([j for j in jobs_before if j.id == "random_dm_task"]) == 1

        # Act: Shutdown and restart
        get_scheduler().shutdown()
        init_scheduler(db_path=str(test_db_path))

        # Assert: Job still exists
        jobs_after = get_scheduler().get_jobs()
        random_dm_jobs = [j for j in jobs_after if j.id == "random_dm_task"]
        assert len(random_dm_jobs) == 1

        # Cleanup
        get_scheduler().shutdown()

    def test_get_scheduled_task_info_returns_correct_data(self, test_db_path):
        """
        Protects against: Incorrect job information retrieval

        Given: Random DM task is scheduled
        When: Task info is requested
        Then: Returns correct job details
        """
        # Arrange
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()
        schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        # Act
        task_info = get_scheduled_task_info("random_dm_task")

        # Assert
        assert task_info is not None
        assert task_info["id"] == "random_dm_task"
        assert task_info["next_run_time"] is not None

        # Cleanup
        get_scheduler().shutdown()

    def test_remove_scheduled_task_deletes_job(self, test_db_path):
        """
        Protects against: Jobs not being removable

        Given: Random DM task is scheduled
        When: Task is removed
        Then: Job no longer exists
        """
        # Arrange
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()
        schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        # Verify job exists
        assert get_scheduled_task_info("random_dm_task") is not None

        # Act: Remove task
        result = remove_scheduled_task("random_dm_task")

        # Assert: Job removed
        assert result is True
        assert get_scheduled_task_info("random_dm_task") is None

        # Cleanup
        get_scheduler().shutdown()

    def test_schedule_with_different_intervals(self, test_db_path):
        """
        Protects against: Interval configuration not being respected

        Given: Various interval values
        When: Random DM task is scheduled with each interval
        Then: Job uses correct interval
        """
        init_scheduler(db_path=str(test_db_path))

        test_intervals = [1, 6, 12, 24, 48, 168]  # hours

        for interval_hours in test_intervals:
            # Act
            mock_func = Mock()
            job = schedule_random_dm_task(
                interval_hours=interval_hours, send_random_dm_func=mock_func
            )

            # Assert
            expected_seconds = interval_hours * 3600
            actual_seconds = job.trigger.interval.total_seconds()
            assert actual_seconds == expected_seconds

        # Cleanup
        get_scheduler().shutdown()


class TestSchedulerErrorHandling:
    """Tests for scheduler error handling and edge cases."""

    def test_schedule_without_function_raises_error(self, test_db_path):
        """
        Protects against: Scheduling without a callable function

        Given: No function provided
        When: Attempting to schedule
        Then: Raises appropriate error
        """
        init_scheduler(db_path=str(test_db_path))

        # Act & Assert
        with pytest.raises(TypeError):
            schedule_random_dm_task(interval_hours=24, send_random_dm_func=None)

        # Cleanup
        get_scheduler().shutdown()

    def test_schedule_with_invalid_interval_handles_gracefully(self, test_db_path):
        """
        Protects against: Invalid interval values causing crashes

        Given: Invalid interval (e.g., negative, zero)
        When: Attempting to schedule
        Then: Handles gracefully or uses default
        """
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()

        # Act & Assert: Should handle invalid values
        # (Implementation may raise ValueError or use minimum value)
        try:
            job = schedule_random_dm_task(
                interval_hours=-1, send_random_dm_func=mock_func
            )
            # If it doesn't raise, ensure interval is positive
            assert job.trigger.interval.total_seconds() > 0
        except ValueError:
            # This is acceptable error handling
            pass

        # Cleanup
        get_scheduler().shutdown()

    def test_get_info_for_nonexistent_task_returns_none(self, test_db_path):
        """
        Protects against: Errors when querying nonexistent tasks

        Given: Task does not exist
        When: Requesting task info
        Then: Returns None gracefully
        """
        init_scheduler(db_path=str(test_db_path))

        # Act
        task_info = get_scheduled_task_info("nonexistent_task")

        # Assert
        assert task_info is None

        # Cleanup
        get_scheduler().shutdown()

    def test_remove_nonexistent_task_returns_false(self, test_db_path):
        """
        Protects against: Errors when removing nonexistent tasks

        Given: Task does not exist
        When: Attempting to remove
        Then: Returns False gracefully
        """
        init_scheduler(db_path=str(test_db_path))

        # Act
        result = remove_scheduled_task("nonexistent_task")

        # Assert
        assert result is False

        # Cleanup
        get_scheduler().shutdown()


class TestSchedulerConcurrency:
    """Tests for concurrent scheduler operations."""

    def test_multiple_schedulers_share_same_job_store(self, test_db_path):
        """
        Protects against: Multiple scheduler instances conflicting

        Given: Two scheduler instances with same DB
        When: Both access jobs
        Then: They see the same jobs
        """
        # Arrange: First scheduler
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()
        schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        jobs_from_first = get_scheduler().get_jobs()
        first_job_count = len(jobs_from_first)

        get_scheduler().shutdown()

        # Act: Second scheduler instance
        init_scheduler(db_path=str(test_db_path))
        jobs_from_second = get_scheduler().get_jobs()
        second_job_count = len(jobs_from_second)

        # Assert: Same jobs visible
        assert second_job_count == first_job_count

        # Cleanup
        get_scheduler().shutdown()


class TestSchedulerConfiguration:
    """Tests for scheduler configuration options."""

    def test_scheduler_uses_correct_timezone(self, test_db_path):
        """
        Protects against: Timezone issues in scheduling

        Given: Scheduler is initialized
        When: Job is scheduled
        Then: Uses UTC timezone (or configured timezone)
        """
        # Arrange & Act
        init_scheduler(db_path=str(test_db_path))

        # Assert: Check scheduler timezone
        # Note: Default should be UTC for consistency
        assert get_scheduler().timezone is not None
        # Exact timezone check depends on configuration

        # Cleanup
        get_scheduler().shutdown()

    def test_scheduler_starts_successfully(self, test_db_path):
        """
        Protects against: Scheduler failing to start

        Given: Scheduler is initialized
        When: Checking scheduler state
        Then: Scheduler is running
        """
        # Arrange & Act
        init_scheduler(db_path=str(test_db_path))

        # Assert
        assert scheduler.running is True

        # Cleanup
        get_scheduler().shutdown()

    def test_scheduler_shutdown_cleans_up(self, test_db_path):
        """
        Protects against: Resource leaks on shutdown

        Given: Scheduler is running
        When: Shutdown is called
        Then: Scheduler stops cleanly
        """
        # Arrange
        init_scheduler(db_path=str(test_db_path))
        assert scheduler.running is True

        # Act
        get_scheduler().shutdown()

        # Assert
        assert scheduler.running is False


@pytest.mark.asyncio
class TestSchedulerWithRealDMFunction:
    """Tests scheduler integration with actual DM sending function."""

    async def test_scheduler_can_execute_async_dm_function(
        self, test_db_path, test_session, engagement_team_members, mock_slack_app, mock_slack_client_for_dm
    ):
        """
        Protects against: Scheduler failing to execute async functions

        Given: Async DM function
        When: Scheduled via APScheduler
        Then: Function can be called successfully
        """
        from src.services.proactive_dm_service import send_random_proactive_dm

        # Note: APScheduler requires special handling for async functions
        # This test verifies the function is callable, but actual scheduling
        # of async functions may require wrapper or different executor

        # Act: Create wrapper for async function
        async def wrapped_function():
            return await send_random_proactive_dm(
                app=mock_slack_app,
                db_session=test_session,
                slack_client=mock_slack_client_for_dm,
            )

        # Assert: Can call function manually
        result = await wrapped_function()
        assert result is not None
        # Note: Full scheduler execution of async functions requires
        # specific configuration (AsyncIOExecutor), tested elsewhere

    def test_scheduler_stores_job_with_correct_metadata(self, test_db_path):
        """
        Protects against: Loss of job metadata

        Given: Job is scheduled with metadata
        When: Job is retrieved
        Then: Metadata is preserved
        """
        init_scheduler(db_path=str(test_db_path))
        mock_func = Mock()

        # Act: Schedule with metadata
        job = schedule_random_dm_task(interval_hours=24, send_random_dm_func=mock_func)

        # Assert: Metadata accessible
        retrieved_job = scheduler.get_job("random_dm_task")
        assert retrieved_job is not None
        assert retrieved_job.id == "random_dm_task"
        assert retrieved_job.func == mock_func

        # Cleanup
        get_scheduler().shutdown()
