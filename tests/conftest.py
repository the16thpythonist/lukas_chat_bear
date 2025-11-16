"""
Pytest configuration and fixtures for database testing.

Provides shared test fixtures for database setup, cleanup, and test data seeding.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base, TeamMember, ConversationSession, Message, Configuration
from src.repositories.conversation_repo import ConversationRepository
from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.config_repo import ConfigurationRepository


@pytest.fixture(scope="function")
def test_db_path() -> Generator[Path, None, None]:
    """
    Create a temporary database file for testing.

    Automatically cleans up the file after the test completes. File-based SQLite
    is used instead of in-memory to better match production behavior and support
    connection pooling tests.

    Yields:
        Path to temporary test database file
    """
    # Create temporary file for test database
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_lukas_")
    os.close(fd)  # Close file descriptor, SQLAlchemy will open it

    db_path = Path(path)

    yield db_path

    # Cleanup: Remove test database file after test completes
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="function")
def test_engine(test_db_path: Path) -> Generator[Engine, None, None]:
    """
    Create a SQLAlchemy engine for the test database.

    Configures SQLite with the same pragmas as production (foreign keys, WAL mode)
    to ensure test behavior matches production. Creates all tables from models.

    Args:
        test_db_path: Path to test database file

    Yields:
        Configured SQLAlchemy engine
    """
    # Create engine with SQLite optimizations matching production
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        echo=False,  # Disable SQL logging in tests for cleaner output
        connect_args={"check_same_thread": False},  # Allow multi-thread access
    )

    # Enable SQLite pragmas for foreign key support and performance
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    # Create all tables from models
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Dispose of engine connections
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine: Engine) -> Generator[Session, None, None]:
    """
    Create a database session for testing with automatic rollback.

    Each test gets a fresh session that is rolled back after the test completes,
    ensuring test isolation. This allows tests to modify the database without
    affecting other tests.

    Args:
        test_engine: Test database engine

    Yields:
        Database session for the test
    """
    # Create session factory
    SessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = SessionLocal()

    yield session

    # Cleanup: Rollback any changes and close session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def seeded_db(test_session: Session) -> Session:
    """
    Provide a database session pre-populated with common test data.

    Seeds the database with:
    - 3 team members (1 admin, 1 bot, 1 regular user)
    - 2 active conversations with messages
    - Default configuration values

    This fixture is useful for tests that need realistic data to query against
    without having to set up the same test data in every test.

    Args:
        test_session: Empty test database session

    Returns:
        Database session with seeded test data
    """
    # Seed team members
    admin = TeamMember(
        slack_user_id="U001_ADMIN",
        display_name="Admin User",
        real_name="Admin McAdmin",
        is_admin=True,
        is_bot=False,
        is_active=True,
        total_messages_sent=50,
    )

    bot_user = TeamMember(
        slack_user_id="U002_BOT",
        display_name="Bot User",
        real_name="Bot McBot",
        is_admin=False,
        is_bot=True,
        is_active=True,
        total_messages_sent=0,
    )

    regular_user = TeamMember(
        slack_user_id="U003_REGULAR",
        display_name="Regular User",
        real_name="Regular Person",
        is_admin=False,
        is_bot=False,
        is_active=True,
        total_messages_sent=25,
        last_proactive_dm_at=datetime.utcnow() - timedelta(days=2),
    )

    test_session.add_all([admin, bot_user, regular_user])
    test_session.flush()  # Get IDs without committing

    # Seed conversations
    conv1 = ConversationSession(
        team_member_id=admin.id,
        channel_type="dm",
        channel_id="C001",
        thread_ts=None,
        message_count=3,
        total_tokens=150,
        is_active=True,
    )

    conv2 = ConversationSession(
        team_member_id=regular_user.id,
        channel_type="channel",
        channel_id="C002",
        thread_ts="1234567890.123456",
        message_count=2,
        total_tokens=100,
        is_active=True,
    )

    test_session.add_all([conv1, conv2])
    test_session.flush()

    # Seed messages
    msg1 = Message(
        conversation_id=conv1.id,
        sender_type="user",
        content="Hello Lukas!",
        slack_ts="1234567890.111111",
        token_count=5,
    )

    msg2 = Message(
        conversation_id=conv1.id,
        sender_type="bot",
        content="Hi there! How can I help?",
        slack_ts="1234567890.222222",
        token_count=10,
    )

    msg3 = Message(
        conversation_id=conv2.id,
        sender_type="user",
        content="Question about the project",
        slack_ts="1234567890.333333",
        token_count=8,
    )

    test_session.add_all([msg1, msg2, msg3])

    # Seed default configurations
    configs = [
        Configuration(
            key="random_dm_interval_hours",
            value="24",
            value_type="integer",
            description="Hours between random DM sends",
        ),
        Configuration(
            key="proactive_engagement_probability",
            value="0.15",
            value_type="float",
            description="Probability of engaging in conversations",
        ),
        Configuration(
            key="enable_image_generation",
            value="true",
            value_type="boolean",
            description="Enable DALL-E image generation",
        ),
    ]

    test_session.add_all(configs)
    test_session.commit()

    return test_session


@pytest.fixture(scope="function")
def conversation_repo(test_session: Session) -> ConversationRepository:
    """Provide ConversationRepository instance for testing."""
    return ConversationRepository(test_session)


@pytest.fixture(scope="function")
def team_member_repo(test_session: Session) -> TeamMemberRepository:
    """Provide TeamMemberRepository instance for testing."""
    return TeamMemberRepository(test_session)


@pytest.fixture(scope="function")
def config_repo(test_session: Session) -> ConfigurationRepository:
    """Provide ConfigurationRepository instance for testing."""
    return ConfigurationRepository(test_session)


# ============================================================================
# Phase 4: Proactive Engagement Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def engagement_team_members(test_session: Session) -> list[TeamMember]:
    """
    Provide realistic team members for engagement testing.

    Creates 7 team members with varied states:
    - 5 active users with different last_proactive_dm_at times
    - 1 bot user (should be excluded)
    - 1 inactive user (should be excluded)

    Returns:
        List of TeamMember instances committed to test database
    """
    from unittest.mock import Mock

    members = [
        # Never contacted - highest priority for DM
        TeamMember(
            slack_user_id="U_NEVER",
            display_name="Never Contacted",
            real_name="Never Contact",
            is_admin=False,
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=None,
            total_messages_sent=0,
        ),
        # Contacted 7 days ago - second priority
        TeamMember(
            slack_user_id="U_WEEK_AGO",
            display_name="Contacted Week Ago",
            real_name="Week Ago",
            is_admin=False,
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.utcnow() - timedelta(days=7),
            total_messages_sent=10,
        ),
        # Contacted 2 days ago
        TeamMember(
            slack_user_id="U_TWO_DAYS",
            display_name="Contacted Two Days",
            real_name="Two Days",
            is_admin=False,
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.utcnow() - timedelta(days=2),
            total_messages_sent=20,
        ),
        # Contacted 1 hour ago - lowest priority
        TeamMember(
            slack_user_id="U_RECENT",
            display_name="Contacted Recently",
            real_name="Recent",
            is_admin=False,
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.utcnow() - timedelta(hours=1),
            total_messages_sent=30,
        ),
        # Admin user
        TeamMember(
            slack_user_id="U_ADMIN",
            display_name="Admin User",
            real_name="Admin Person",
            is_admin=True,
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.utcnow() - timedelta(days=5),
            total_messages_sent=50,
        ),
        # Bot user - should be EXCLUDED
        TeamMember(
            slack_user_id="B_BOT",
            display_name="Bot User",
            real_name="Bot",
            is_admin=False,
            is_bot=True,
            is_active=True,
            last_proactive_dm_at=None,
            total_messages_sent=0,
        ),
        # Inactive user - should be EXCLUDED
        TeamMember(
            slack_user_id="U_INACTIVE",
            display_name="Inactive User",
            real_name="Inactive",
            is_admin=False,
            is_bot=False,
            is_active=False,
            last_proactive_dm_at=datetime.utcnow() - timedelta(days=30),
            total_messages_sent=5,
        ),
    ]

    test_session.add_all(members)
    test_session.commit()

    return members


@pytest.fixture(scope="function")
def engagement_config(test_session: Session) -> list[Configuration]:
    """
    Provide pre-seeded engagement configuration for testing.

    Creates configuration entries for:
    - thread_response_probability: 0.20 (20%)
    - random_dm_interval_hours: 24
    - active_hours: {"start_hour": 8, "end_hour": 18}

    Also patches the config loader to use these test values instead of config.yml.

    Returns:
        List of Configuration instances committed to test database
    """
    import json
    from unittest.mock import patch

    configs = [
        Configuration(
            key="thread_response_probability",
            value="0.20",
            value_type="float",
            description="Probability of responding to threads (0.0-1.0)",
        ),
        Configuration(
            key="random_dm_interval_hours",
            value="24",
            value_type="integer",
            description="Hours between random DM sends",
        ),
        Configuration(
            key="active_hours",
            value=json.dumps({"start_hour": 8, "end_hour": 18}),
            value_type="json",
            description="Active hours for proactive engagement",
        ),
    ]

    test_session.add_all(configs)
    test_session.commit()

    # Patch config loader to return test values
    test_config = {
        "bot": {
            "engagement": {
                "thread_response_probability": 0.20,
                "reaction_probability": 0.15,
                "active_hours": {
                    "start_hour": 8,
                    "end_hour": 18,
                    "timezone": "UTC"
                }
            },
            "random_dm": {
                "interval_hours": 24
            }
        }
    }

    # Patch the config object used by EngagementService
    with patch('src.utils.config_loader.config', test_config):
        yield configs


@pytest.fixture(scope="function")
def mock_slack_client():
    """
    Provide mock Slack WebClient for testing.

    Mocks:
    - conversations_replies: Returns sample thread messages
    - reactions_add: Tracks reaction additions
    - chat_postMessage: Tracks sent messages

    Returns:
        Mock Slack client with configured methods
    """
    from unittest.mock import Mock, AsyncMock

    client = Mock()

    # Mock conversations_replies for thread fetching (async method)
    client.conversations_replies = AsyncMock(return_value={
        "messages": [
            {"user": "U11111", "text": "Question", "ts": "1000.0"},
            {"user": "U22222", "text": "Answer", "ts": "1000.1"},
            {"user": "U33333", "text": "Follow-up", "ts": "1000.2"},
        ]
    })

    # Mock reactions_add for emoji reactions (async method)
    client.reactions_add = AsyncMock(return_value={"ok": True})

    # Mock chat_postMessage for sending messages (async method)
    client.chat_postMessage = AsyncMock(return_value={
        "ok": True,
        "ts": "1234567890.123456",
        "message": {"text": "Response"}
    })

    return client


@pytest.fixture(scope="function")
def mock_slack_app(mock_slack_client):
    """
    Provide mock Slack Bolt App for testing.

    Includes mock client and event decorator registration.

    Args:
        mock_slack_client: Mocked Slack client

    Returns:
        Mock Slack Bolt App
    """
    from unittest.mock import Mock

    app = Mock()
    app.client = mock_slack_client

    # Mock event decorator
    def event_decorator(event_type):
        def decorator(func):
            return func
        return decorator

    app.event = event_decorator

    return app


@pytest.fixture(scope="function")
def engagement_service_instance(test_session: Session, team_member_repo, config_repo):
    """
    Provide real EngagementService instance for testing.

    Uses real database session and repositories to test actual
    database operations and business logic.

    Args:
        test_session: Test database session
        team_member_repo: TeamMemberRepository instance
        config_repo: ConfigurationRepository instance

    Returns:
        EngagementService instance with real dependencies
    """
    from src.services.engagement_service import EngagementService

    return EngagementService(
        db_session=test_session,
        team_member_repo=team_member_repo,
        config_repo=config_repo,
    )


@pytest.fixture(scope="function")
def sample_thread_messages():
    """
    Provide realistic Slack thread conversation data.

    Returns a 5-message thread with:
    - Initial question
    - 3 responses from different users
    - 1 bot message (to test filtering)

    Returns:
        Dict with Slack thread messages structure
    """
    return {
        "messages": [
            {
                "type": "message",
                "user": "U_ALICE",
                "text": "What do you all think about the new feature?",
                "ts": "1234567890.000000",
                "thread_ts": "1234567890.000000",
            },
            {
                "type": "message",
                "user": "U_BOB",
                "text": "I think it's a great addition!",
                "ts": "1234567890.100000",
                "thread_ts": "1234567890.000000",
            },
            {
                "type": "message",
                "user": "U_CHARLIE",
                "text": "Agreed, but we should test it more.",
                "ts": "1234567890.200000",
                "thread_ts": "1234567890.000000",
            },
            {
                "type": "message",
                "bot_id": "B_SOMEBOT",
                "text": "Automated deployment notification",
                "ts": "1234567890.300000",
                "thread_ts": "1234567890.000000",
            },
            {
                "type": "message",
                "user": "U_DIANA",
                "text": "When can we release?",
                "ts": "1234567890.400000",
                "thread_ts": "1234567890.000000",
            },
        ]
    }


@pytest.fixture(scope="function")
def mock_slack_client_for_dm(mock_slack_client):
    """
    Extend mock Slack client with DM-specific mocking.

    Adds mocks for:
    - conversations_open: Opens DM channel with user
    - Ensures chat_postMessage is already mocked

    Args:
        mock_slack_client: Base mock Slack client

    Returns:
        Mock Slack client configured for DM testing
    """
    from unittest.mock import AsyncMock

    # Mock conversations_open for DM creation (async method)
    mock_slack_client.conversations_open = AsyncMock(return_value={
        "ok": True,
        "channel": {
            "id": "D12345TEST",
            "is_im": True,
        }
    })

    return mock_slack_client


@pytest.fixture(scope="function")
def proactive_dm_service(test_session: Session, engagement_service_instance):
    """
    Provide ProactiveDMService instance for testing.

    Args:
        test_session: Test database session
        engagement_service_instance: EngagementService instance

    Returns:
        ProactiveDMService instance with real dependencies
    """
    from src.services.proactive_dm_service import ProactiveDMService

    return ProactiveDMService(
        db_session=test_session,
        engagement_service=engagement_service_instance,
    )
