"""
Tests for Alembic database migrations.

Tests that migrations can be applied and reverted correctly.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


@pytest.mark.skip(reason="Alembic tests require additional environment setup")
class TestAlembicMigrations:
    """Test Alembic migration operations."""

    @pytest.fixture
    def alembic_config(self, test_db_path: Path) -> Config:
        """
        Create Alembic config for testing.

        Sets up Alembic configuration to use the test database.

        Args:
            test_db_path: Path to test database file

        Returns:
            Alembic Config object
        """
        # Get path to alembic.ini in project root
        project_root = Path(__file__).parent.parent.parent
        alembic_ini = project_root / "alembic.ini"

        config = Config(str(alembic_ini))
        # Override database URL to use test database
        config.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")

        return config

    def test_upgrade_creates_all_tables(self, test_db_path: Path, alembic_config: Config):
        """
        Test that running 'alembic upgrade head' creates all tables.

        Protects against: Migration failures, incomplete schema creation.
        """
        # Run upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify all tables created
        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result}

        expected_tables = {
            "team_members",
            "conversation_sessions",
            "messages",
            "scheduled_tasks",
            "configurations",
            "engagement_events",
            "generated_images",
            "alembic_version",  # Alembic tracking table
        }

        assert expected_tables.issubset(tables), \
            f"Missing tables: {expected_tables - tables}"

    def test_downgrade_removes_tables(self, test_db_path: Path, alembic_config: Config):
        """
        Test that running 'alembic downgrade base' removes all tables.

        Migration downgrade should cleanly remove schema.

        Protects against: Irreversible migrations, downgrade failures.
        """
        # First upgrade to head
        command.upgrade(alembic_config, "head")

        # Then downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify tables removed (except alembic_version which always remains)
        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result}

        application_tables = {
            "team_members",
            "conversation_sessions",
            "messages",
            "scheduled_tasks",
            "configurations",
            "engagement_events",
            "generated_images",
        }

        # No application tables should remain
        assert len(application_tables & tables) == 0, \
            f"Tables still exist after downgrade: {application_tables & tables}"

    def test_upgrade_downgrade_cycle(self, test_db_path: Path, alembic_config: Config):
        """
        Test that upgrade -> downgrade -> upgrade cycle works correctly.

        Should be able to repeatedly apply and revert migrations.

        Protects against: State corruption, non-repeatable migrations.
        """
        # Upgrade
        command.upgrade(alembic_config, "head")

        # Downgrade
        command.downgrade(alembic_config, "base")

        # Upgrade again - should work without errors
        command.upgrade(alembic_config, "head")

        # Verify tables exist after second upgrade
        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result}

        assert "team_members" in tables
        assert "messages" in tables

    def test_migration_creates_indexes(self, test_db_path: Path, alembic_config: Config):
        """
        Test that migrations create database indexes.

        Indexes are critical for query performance.

        Protects against: Missing indexes, poor query performance.
        """
        command.upgrade(alembic_config, "head")

        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            # Query for indexes
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index'")
            )
            indexes = {row[0] for row in result}

        # Verify some expected indexes exist
        expected_indexes = {
            "ix_team_members_slack_user_id",
            "ix_conversation_sessions_team_member_id",
            "ix_messages_conversation_id",
            "ix_messages_timestamp",
            "ix_configurations_key",
        }

        # Note: SQLite may have additional auto-generated indexes
        assert expected_indexes.issubset(indexes), \
            f"Missing indexes: {expected_indexes - indexes}"

    def test_migration_creates_foreign_keys(self, test_db_path: Path, alembic_config: Config):
        """
        Test that migrations create foreign key constraints.

        Foreign keys enforce referential integrity.

        Protects against: Missing FK constraints, orphaned records.
        """
        command.upgrade(alembic_config, "head")

        engine = create_engine(f"sqlite:///{test_db_path}")

        # Enable foreign keys
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

            # Create a team member
            conn.execute(text("""
                INSERT INTO team_members (id, slack_user_id, display_name, is_active, is_bot, total_messages_sent)
                VALUES ('test-member-id', 'U12345', 'Test User', 1, 0, 0)
            """))
            conn.commit()

            # Create a conversation referencing the team member
            conn.execute(text("""
                INSERT INTO conversation_sessions (
                    id, team_member_id, channel_type, channel_id,
                    message_count, total_tokens, is_active
                )
                VALUES ('test-conv-id', 'test-member-id', 'dm', 'C12345', 0, 0, 1)
            """))
            conn.commit()

            # Try to delete team member (should fail due to FK)
            with pytest.raises(Exception) as exc_info:
                conn.execute(text("DELETE FROM team_members WHERE id = 'test-member-id'"))
                conn.commit()

            # Verify it's a foreign key error
            assert "foreign key" in str(exc_info.value).lower() or \
                   "constraint" in str(exc_info.value).lower()

    def test_migration_version_tracked(self, test_db_path: Path, alembic_config: Config):
        """
        Test that Alembic tracks the current migration version.

        Version tracking allows Alembic to know which migrations have been applied.

        Protects against: Migration state confusion, duplicate applications.
        """
        command.upgrade(alembic_config, "head")

        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()

        # Should have a version (migration ID)
        assert version is not None
        assert len(version) > 0

    def test_current_migration_matches_models(self, test_db_path: Path, alembic_config: Config):
        """
        Test that current migration creates schema matching SQLAlchemy models.

        Migration should create the same schema as Base.metadata.create_all().

        Protects against: Migration drift, model-schema mismatch.
        """
        # Create schema using Alembic migration
        command.upgrade(alembic_config, "head")

        # Get table list from migrated database
        engine = create_engine(f"sqlite:///{test_db_path}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            migrated_tables = {row[0] for row in result}

        # Remove alembic_version table (only exists in migrated DB)
        migrated_tables.discard("alembic_version")

        # Create schema using SQLAlchemy models
        from src.models import Base

        test_db_path_2 = Path(tempfile.mktemp(suffix=".db"))
        engine_2 = create_engine(f"sqlite:///{test_db_path_2}")
        Base.metadata.create_all(engine_2)

        with engine_2.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            model_tables = {row[0] for row in result}

        # Cleanup
        engine_2.dispose()
        if test_db_path_2.exists():
            test_db_path_2.unlink()

        # Tables should match
        assert migrated_tables == model_tables, \
            f"Migration tables != Model tables. Diff: {migrated_tables ^ model_tables}"
