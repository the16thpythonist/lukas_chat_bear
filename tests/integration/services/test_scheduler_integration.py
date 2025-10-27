"""
Integration tests for SchedulerService.

Tests APScheduler integration including job scheduling, persistence, and shutdown.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import time

from src.services import scheduler_service


# Reset scheduler state before each test
@pytest.fixture(autouse=True)
def reset_scheduler():
    """Reset global scheduler state before each test."""
    # Shutdown any existing scheduler
    if scheduler_service.scheduler is not None:
        try:
            scheduler_service.scheduler.shutdown(wait=False)
        except:
            pass
        scheduler_service.scheduler = None

    yield

    # Cleanup after test
    if scheduler_service.scheduler is not None:
        try:
            scheduler_service.scheduler.shutdown(wait=False)
        except:
            pass
        scheduler_service.scheduler = None


class TestSchedulerInitialization:
    """Test scheduler initialization and configuration."""

    def test_init_scheduler_creates_instance(self, test_db_path):
        """Should create and start APScheduler instance."""
        # When initializing scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler = scheduler_service.init_scheduler()

        # Then scheduler should be created and running
        assert scheduler is not None
        assert scheduler.running is True

        # Cleanup
        scheduler.shutdown(wait=False)

    def test_init_scheduler_is_idempotent(self, test_db_path):
        """Calling init_scheduler multiple times should return same instance."""
        # When initializing scheduler twice
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler1 = scheduler_service.init_scheduler()
            scheduler2 = scheduler_service.init_scheduler()

        # Then should return same instance
        assert scheduler1 is scheduler2

        # Cleanup
        scheduler1.shutdown(wait=False)

    def test_get_scheduler_returns_instance(self, test_db_path):
        """Should return initialized scheduler instance."""
        # Given initialized scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler_service.init_scheduler()

            # When getting scheduler
            scheduler = scheduler_service.get_scheduler()

        # Then should return instance
        assert scheduler is not None
        assert scheduler.running is True

        # Cleanup
        scheduler.shutdown(wait=False)

    def test_get_scheduler_raises_when_not_initialized(self):
        """Should raise RuntimeError when scheduler not initialized."""
        # When getting scheduler before initialization
        # Then should raise error
        with pytest.raises(RuntimeError, match="Scheduler not initialized"):
            scheduler_service.get_scheduler()


class TestJobScheduling:
    """Test job scheduling and execution."""

    def test_schedule_random_dm_task(self, test_db_path):
        """Should schedule random DM task with correct interval."""
        # Given initialized scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler_service.init_scheduler()

            # Mock DM function
            mock_dm_func = Mock()

            # When scheduling random DM task
            scheduler_service.schedule_random_dm_task(
                interval_hours=24,
                send_random_dm_func=mock_dm_func
            )

            # Then job should be scheduled
            scheduler = scheduler_service.get_scheduler()
            jobs = scheduler.get_jobs()

            assert len(jobs) >= 1
            random_dm_job = scheduler.get_job('random_dm_task')
            assert random_dm_job is not None

            # Cleanup
            scheduler.shutdown(wait=False)

    def test_schedule_random_dm_task_replaces_existing(self, test_db_path):
        """Scheduling same task twice should replace existing job."""
        # Given scheduler with existing random DM task
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler_service.init_scheduler()

            mock_dm_func1 = Mock()
            mock_dm_func2 = Mock()

            scheduler_service.schedule_random_dm_task(
                interval_hours=12,
                send_random_dm_func=mock_dm_func1
            )

            # When scheduling again with different interval
            scheduler_service.schedule_random_dm_task(
                interval_hours=24,
                send_random_dm_func=mock_dm_func2
            )

            # Then should only have one random_dm_task job
            scheduler = scheduler_service.get_scheduler()
            jobs = [j for j in scheduler.get_jobs() if j.id == 'random_dm_task']
            assert len(jobs) == 1

            # Cleanup
            scheduler.shutdown(wait=False)

    def test_schedule_random_dm_task_without_function(self, test_db_path):
        """Should skip scheduling when no function provided."""
        # Given initialized scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler_service.init_scheduler()

            # When scheduling without function
            scheduler_service.schedule_random_dm_task(
                interval_hours=24,
                send_random_dm_func=None
            )

            # Then should not create job
            scheduler = scheduler_service.get_scheduler()
            random_dm_job = scheduler.get_job('random_dm_task')
            assert random_dm_job is None

            # Cleanup
            scheduler.shutdown(wait=False)


class TestSchedulerShutdown:
    """Test scheduler shutdown behavior."""

    def test_shutdown_scheduler_stops_running(self, test_db_path):
        """Should stop scheduler gracefully."""
        # Given running scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler = scheduler_service.init_scheduler()
            assert scheduler.running is True

            # When shutting down
            scheduler_service.shutdown_scheduler()

            # Then scheduler should be stopped
            assert scheduler.running is False
            assert scheduler_service.scheduler is None

    def test_shutdown_scheduler_when_not_initialized(self):
        """Should handle shutdown when scheduler not initialized."""
        # When shutting down non-existent scheduler
        # Then should not raise error
        scheduler_service.shutdown_scheduler()

        # Verify scheduler is still None
        assert scheduler_service.scheduler is None


class TestSchedulerPersistence:
    """Test scheduler job persistence across restarts."""

    def test_scheduler_uses_database_jobstore(self, test_db_path):
        """Scheduler should be configured to use database job store."""
        # When initializing scheduler
        with patch.dict('os.environ', {'DATABASE_URL': f'sqlite:///{test_db_path}'}):
            scheduler = scheduler_service.init_scheduler()

            # Then should have SQLAlchemy jobstore configured
            assert 'default' in scheduler._jobstores
            jobstore = scheduler._jobstores['default']
            assert jobstore.__class__.__name__ == 'SQLAlchemyJobStore'

            # Cleanup
            scheduler.shutdown(wait=False)
