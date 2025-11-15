"""
Pytest configuration and fixtures for dashboard backend tests.
Provides test fixtures for Flask app, client, and database mocking.
"""
import pytest
from backend.app import create_app
from backend.config import Config


class TestConfig(Config):
    """Test configuration with overrides for testing."""
    TESTING = True
    DEBUG = True
    DASHBOARD_ADMIN_PASSWORD = 'test_password_123'
    DATABASE_URI = 'sqlite:///:memory:'  # In-memory database for tests
    SESSION_TYPE = 'null'  # Don't persist sessions in tests
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    """
    Create and configure a Flask app instance for testing.

    Yields:
        Flask app configured for testing
    """
    # Reset database module state before creating app
    import backend.services.database as db_module
    db_module._engine = None
    db_module._SessionFactory = None

    app = create_app()
    app.config.from_object(TestConfig)

    # Initialize database with test config (in-memory SQLite)
    from backend.services.database import init_database
    from src.models import Base

    init_database(app)

    # Create all tables in the test database
    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    # Set up application context
    with app.app_context():
        yield app

    # Clean up database after test
    Base.metadata.drop_all(engine)
    db_module.cleanup_database()


@pytest.fixture
def client(app):
    """
    Create a test client for the Flask app.

    Args:
        app: Flask app fixture

    Yields:
        Flask test client
    """
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """
    Create an authenticated test client.

    Args:
        client: Flask test client fixture

    Yields:
        Authenticated Flask test client
    """
    # Log in
    client.post('/api/auth/login', json={'password': 'test_password_123'})
    yield client
    # Log out
    client.post('/api/auth/logout')


@pytest.fixture
def runner(app):
    """
    Create a test CLI runner for the Flask app.

    Args:
        app: Flask app fixture

    Yields:
        Flask CLI test runner
    """
    return app.test_cli_runner()


# Database fixtures
@pytest.fixture
def db_session():
    """
    Create a database session for tests with clean state.

    Yields:
        SQLAlchemy session with in-memory database
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.models import Base

    # Create in-memory database
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


# Test data fixtures
@pytest.fixture
def sample_team_members(db_session):
    """Create sample team members for testing."""
    from src.models.team_member import TeamMember
    from datetime import datetime

    members = [
        TeamMember(
            slack_user_id='U001',
            display_name='Alice',
            real_name='Alice Smith',
            is_bot=False
        ),
        TeamMember(
            slack_user_id='U002',
            display_name='Bob',
            real_name='Bob Johnson',
            is_bot=False
        ),
        TeamMember(
            slack_user_id='LUKAS_BOT',
            display_name='Lukas the Bear (Bot)',
            real_name='Lukas',
            is_bot=True
        )
    ]

    for member in members:
        db_session.add(member)

    db_session.commit()
    return members


@pytest.fixture
def sample_conversations(db_session, sample_team_members):
    """Create sample conversations for testing."""
    from src.models.conversation import ConversationSession
    from datetime import datetime, timedelta

    conversations = [
        ConversationSession(
            id='conv_001',
            channel_id='C001',
            channel_type='dm',
            team_member_id=sample_team_members[0].id,
            created_at=datetime.utcnow() - timedelta(days=5),
            last_message_at=datetime.utcnow() - timedelta(days=5)
        ),
        ConversationSession(
            id='conv_002',
            channel_id='C002',
            channel_type='channel',
            team_member_id=sample_team_members[1].id,
            created_at=datetime.utcnow() - timedelta(days=3),
            last_message_at=datetime.utcnow() - timedelta(days=3)
        )
    ]

    for conv in conversations:
        db_session.add(conv)

    db_session.commit()
    return conversations


@pytest.fixture
def sample_messages(db_session, sample_conversations):
    """Create sample messages for testing."""
    from src.models.message import Message
    from datetime import datetime, timedelta

    messages = []

    # Create 20 messages over the last 5 days
    for i in range(20):
        msg = Message(
            id=f'msg_{i:03d}',
            conversation_id=sample_conversations[i % 2].id,
            sender_type='bot',
            content=f'Test message {i}',
            timestamp=datetime.utcnow() - timedelta(days=5-i/4, hours=i),
            token_count=10
        )
        messages.append(msg)
        db_session.add(msg)

    db_session.commit()
    return messages


@pytest.fixture
def sample_images(db_session):
    """Create sample generated images for testing."""
    from src.models.generated_image import GeneratedImage
    from datetime import datetime, timedelta

    images = []
    statuses = ['generated', 'posted', 'failed']

    for i in range(10):
        img = GeneratedImage(
            id=f'img_{i:03d}',
            prompt=f'A cute bear doing activity {i}',
            image_url=f'https://example.com/image_{i}.png' if i % 3 != 2 else None,
            status=statuses[i % 3],
            created_at=datetime.utcnow() - timedelta(days=10-i),
            posted_at=datetime.utcnow() - timedelta(days=9-i) if i % 3 == 1 else None,
            posted_to_channel='C001' if i % 3 == 1 else None,
            error_message='Generation failed' if i % 3 == 2 else None
        )
        images.append(img)
        db_session.add(img)

    db_session.commit()
    return images


@pytest.fixture
def sample_scheduled_tasks(db_session):
    """Create sample scheduled tasks for testing (unit tests only)."""
    from src.models.scheduled_task import ScheduledTask
    from datetime import datetime, timedelta

    tasks = []

    # Upcoming tasks
    for i in range(3):
        task = ScheduledTask(
            id=f'task_upcoming_{i}',
            job_id=f'job_{i}',
            task_type='random_dm' if i % 2 == 0 else 'image_post',
            target_type='system',
            target_id=None,
            scheduled_at=datetime.utcnow() + timedelta(hours=i+1),
            status='pending',
            retry_count=0,
            meta={'interval_hours': 24} if i % 2 == 0 else {'interval_days': 7}
        )
        tasks.append(task)
        db_session.add(task)

    # Completed tasks
    for i in range(5):
        task = ScheduledTask(
            id=f'task_completed_{i}',
            job_id=f'job_old_{i}',
            task_type='random_dm',
            target_type='user',
            target_id='U001',
            scheduled_at=datetime.utcnow() - timedelta(days=i+1),
            executed_at=datetime.utcnow() - timedelta(days=i+1, minutes=5),
            status='completed' if i % 2 == 0 else 'failed',
            retry_count=0,
            error_message='Test error' if i % 2 == 1 else None,
            meta={'interval_hours': 24}
        )
        tasks.append(task)
        db_session.add(task)

    db_session.commit()
    return tasks


@pytest.fixture
def sample_scheduled_tasks_integration(app):
    """Create sample scheduled tasks in the Flask app's database (integration tests)."""
    from src.models.scheduled_task import ScheduledTask
    from backend.services.database import get_session
    from datetime import datetime, timedelta

    session = get_session()
    tasks = []

    # Upcoming tasks
    for i in range(3):
        task = ScheduledTask(
            id=f'task_upcoming_{i}',
            job_id=f'job_{i}',
            task_type='random_dm' if i % 2 == 0 else 'image_post',
            target_type='system',
            target_id=None,
            scheduled_at=datetime.utcnow() + timedelta(hours=i+1),
            status='pending',
            retry_count=0,
            meta={'interval_hours': 24} if i % 2 == 0 else {'interval_days': 7}
        )
        tasks.append(task)
        session.add(task)

    # Completed tasks
    for i in range(5):
        task = ScheduledTask(
            id=f'task_completed_{i}',
            job_id=f'job_old_{i}',
            task_type='random_dm',
            target_type='user',
            target_id='U001',
            scheduled_at=datetime.utcnow() - timedelta(days=i+1),
            executed_at=datetime.utcnow() - timedelta(days=i+1, minutes=5),
            status='completed' if i % 2 == 0 else 'failed',
            retry_count=0,
            error_message='Test error' if i % 2 == 1 else None,
            meta={'interval_hours': 24}
        )
        tasks.append(task)
        session.add(task)

    session.commit()
    session.close()
    return tasks
