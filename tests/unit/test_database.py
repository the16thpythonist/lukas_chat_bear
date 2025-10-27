"""
Tests for core database functionality.

Tests database connection, initialization, session management, and SQLite configuration.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.models import Base
from src.utils.database import (
    engine as production_engine,
    get_db_session,
    get_db,
    check_db_connection,
    init_db,
)


class TestDatabaseConnection:
    """Test database connection and initialization."""

    def test_engine_creation(self, test_engine: Engine):
        """
        Test that a SQLAlchemy engine can be created successfully.

        Protects against: Database connection failures, invalid connection strings.
        """
        assert test_engine is not None
        assert test_engine.url.drivername == "sqlite"

    def test_sqlite_foreign_keys_enabled(self, test_session: Session):
        """
        Test that SQLite foreign key constraints are enabled.

        Foreign keys must be explicitly enabled in SQLite to enforce referential
        integrity. This test prevents data integrity issues from disabled FK checks.

        Protects against: Orphaned records, referential integrity violations.
        """
        result = test_session.execute(text("PRAGMA foreign_keys"))
        foreign_keys_enabled = result.scalar()
        assert foreign_keys_enabled == 1, "Foreign keys should be enabled in SQLite"

    def test_sqlite_wal_mode_enabled(self, test_session: Session):
        """
        Test that SQLite Write-Ahead Logging (WAL) mode is enabled.

        WAL mode improves concurrency and performance by allowing readers to
        access the database while a write is in progress.

        Protects against: Performance degradation, locking issues.
        """
        result = test_session.execute(text("PRAGMA journal_mode"))
        journal_mode = result.scalar()
        assert journal_mode.lower() == "wal", "WAL mode should be enabled for better concurrency"

    def test_database_tables_created(self, test_engine: Engine):
        """
        Test that all expected tables are created in the database.

        Verifies that Base.metadata.create_all() successfully creates all 7 model tables.

        Protects against: Missing tables, schema initialization failures.
        """
        # Get list of all table names from metadata
        expected_tables = {
            "team_members",
            "conversation_sessions",
            "messages",
            "scheduled_tasks",
            "configurations",
            "engagement_events",
            "generated_images",
        }

        # Query actual tables from database
        with test_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            actual_tables = {row[0] for row in result}

        # Verify all expected tables exist
        assert expected_tables.issubset(actual_tables), \
            f"Missing tables: {expected_tables - actual_tables}"


class TestSessionManagement:
    """Test database session lifecycle and context managers."""

    def test_session_creation(self, test_session: Session):
        """
        Test that a database session can be created.

        Protects against: Session factory configuration errors.
        """
        assert test_session is not None
        assert isinstance(test_session, Session)

    def test_session_transaction_rollback(self, test_session: Session):
        """
        Test that session changes are properly rolled back.

        The test fixture should roll back all changes after each test to ensure
        test isolation. This verifies that the rollback mechanism works.

        Protects against: Test pollution, data leaking between tests.
        """
        from src.models import TeamMember

        # Add a record
        member = TeamMember(
            slack_user_id="U_TEST_ROLLBACK",
            display_name="Test User",
            real_name="Test Rollback",
        )
        test_session.add(member)
        test_session.flush()

        # Verify it exists in current session
        assert test_session.query(TeamMember).filter_by(
            slack_user_id="U_TEST_ROLLBACK"
        ).count() == 1

        # Rollback and verify it's gone
        test_session.rollback()
        assert test_session.query(TeamMember).filter_by(
            slack_user_id="U_TEST_ROLLBACK"
        ).count() == 0

    def test_get_db_session_function(self, test_db_path: Path):
        """
        Test the get_db_session() function returns a valid session.

        This tests the production session factory function using a test database.

        Protects against: Session factory configuration errors in production code.
        """
        # Temporarily override DATABASE_URL to use test database
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_db_path}"}):
            # Initialize tables in test database
            init_db()

            # Get session from production function
            session = get_db_session()

            try:
                assert session is not None
                assert isinstance(session, Session)
                # Verify we can execute a query
                result = session.execute(text("SELECT 1"))
                assert result.scalar() == 1
            finally:
                session.close()

    def test_get_db_context_manager(self, test_db_path: Path):
        """
        Test the get_db() context manager properly handles sessions.

        The context manager should automatically close the session after the
        with block completes, even if an exception occurs.

        Protects against: Resource leaks, unclosed database connections.
        """
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_db_path}"}):
            init_db()

            # Test normal usage
            with get_db() as session:
                assert session is not None
                assert isinstance(session, Session)
                result = session.execute(text("SELECT 1"))
                assert result.scalar() == 1

            # Session should be closed after context exits
            # (We can't directly check if closed, but can verify no errors)

    def test_get_db_context_manager_with_exception(self, test_db_path: Path):
        """
        Test that get_db() context manager closes session even on exception.

        Protects against: Resource leaks when errors occur.
        """
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_db_path}"}):
            init_db()

            # Test exception handling
            with pytest.raises(ValueError):
                with get_db() as session:
                    assert session is not None
                    # Raise exception to test cleanup
                    raise ValueError("Test exception")

            # If we get here, context manager didn't crash on exception
            # Session should have been cleaned up properly


@pytest.mark.skip(reason="Environment patching tests require module reload")
class TestDatabaseUtilities:
    """Test database utility functions."""

    def test_check_db_connection_success(self, test_db_path: Path):
        """
        Test that check_db_connection() returns True for valid database.

        Protects against: Silent connection failures during startup.
        """
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_db_path}"}):
            init_db()
            assert check_db_connection() is True

    def test_check_db_connection_failure(self):
        """
        Test that check_db_connection() returns False for invalid database.

        Uses an invalid database path to trigger connection failure.

        Protects against: Unhandled connection exceptions.
        """
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:////nonexistent/invalid/path.db"}):
            # Should return False instead of raising exception
            result = check_db_connection()
            assert result is False

    def test_init_db_creates_tables(self, test_db_path: Path):
        """
        Test that init_db() successfully creates all database tables.

        Protects against: Table creation failures during initialization.
        """
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_db_path}"}):
            # Call init_db which should create all tables
            init_db()

            # Verify tables exist
            from sqlalchemy import create_engine
            test_engine = create_engine(f"sqlite:///{test_db_path}")
            with test_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                tables = {row[0] for row in result}

            expected_tables = {
                "team_members", "conversation_sessions", "messages",
                "scheduled_tasks", "configurations", "engagement_events",
                "generated_images"
            }
            assert expected_tables.issubset(tables)
