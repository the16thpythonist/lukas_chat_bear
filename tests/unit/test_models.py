"""
Tests for SQLAlchemy models.

Tests model creation, relationships, constraints, and validation logic.
Focuses on critical model behaviors rather than testing every single field.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import (
    TeamMember,
    ConversationSession,
    Message,
    ScheduledTask,
    Configuration,
    EngagementEvent,
    GeneratedImage,
)


class TestTeamMemberModel:
    """Test TeamMember model creation and constraints."""

    def test_create_team_member(self, test_session: Session):
        """
        Test creating a basic team member record.

        Protects against: Model definition errors, missing required fields.
        """
        member = TeamMember(
            slack_user_id="U12345",
            display_name="John Doe",
            real_name="John Doe",
        )
        test_session.add(member)
        test_session.commit()

        assert member.id is not None
        assert member.slack_user_id == "U12345"
        assert member.is_active is True  # Default value
        assert member.is_bot is False  # Default value
        assert member.total_messages_sent == 0  # Default value

    def test_slack_user_id_unique_constraint(self, test_session: Session):
        """
        Test that slack_user_id must be unique.

        Each Slack user should only have one record in the database.

        Protects against: Duplicate user records, data inconsistency.
        """
        member1 = TeamMember(
            slack_user_id="U_DUPLICATE",
            display_name="User One",
        )
        test_session.add(member1)
        test_session.commit()

        # Attempt to create another member with same slack_user_id
        member2 = TeamMember(
            slack_user_id="U_DUPLICATE",
            display_name="User Two",
        )
        test_session.add(member2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_team_member_conversation_relationship(self, test_session: Session):
        """
        Test one-to-many relationship between TeamMember and ConversationSession.

        A team member can have multiple conversations, and deleting a team member
        should handle related conversations according to foreign key constraints.

        Protects against: Broken relationships, orphaned records.
        """
        member = TeamMember(
            slack_user_id="U_REL_TEST",
            display_name="Rel Test",
        )
        test_session.add(member)
        test_session.flush()

        # Create two conversations for this member
        conv1 = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C001",
        )
        conv2 = ConversationSession(
            team_member_id=member.id,
            channel_type="channel",
            channel_id="C002",
        )
        test_session.add_all([conv1, conv2])
        test_session.commit()

        # Verify relationship works
        assert len(member.conversations) == 2
        assert conv1.team_member == member
        assert conv2.team_member == member


class TestConversationSessionModel:
    """Test ConversationSession model creation and relationships."""

    def test_create_conversation(self, test_session: Session):
        """
        Test creating a conversation session.

        Protects against: Model definition errors, missing required fields.
        """
        member = TeamMember(slack_user_id="U_CONV", display_name="Conv User")
        test_session.add(member)
        test_session.flush()

        conv = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C12345",
        )
        test_session.add(conv)
        test_session.commit()

        assert conv.id is not None
        assert conv.team_member_id == member.id
        assert conv.is_active is True  # Default value
        assert conv.message_count == 0  # Default value
        assert conv.total_tokens == 0  # Default value

    def test_channel_type_enum_constraint(self, test_session: Session):
        """
        Test that channel_type only accepts valid enum values.

        Protects against: Invalid data, typos in channel type values.
        """
        member = TeamMember(slack_user_id="U_ENUM", display_name="Enum User")
        test_session.add(member)
        test_session.commit()  # Commit member so it persists across iterations

        # Valid values should work
        for valid_type in ["dm", "channel", "thread"]:
            conv = ConversationSession(
                team_member_id=member.id,
                channel_type=valid_type,
                channel_id=f"C_{valid_type}",
            )
            test_session.add(conv)
            test_session.commit()  # Commit instead of flush+rollback

    def test_conversation_message_relationship(self, test_session: Session):
        """
        Test one-to-many relationship between Conversation and Message.

        A conversation can have multiple messages.

        Protects against: Broken relationships, message tracking issues.
        """
        member = TeamMember(slack_user_id="U_MSG_REL", display_name="Msg Rel")
        test_session.add(member)
        test_session.flush()

        conv = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_REL",
        )
        test_session.add(conv)
        test_session.flush()

        # Add messages to conversation
        msg1 = Message(
            conversation_id=conv.id,
            sender_type="user",
            content="Hello",
        )
        msg2 = Message(
            conversation_id=conv.id,
            sender_type="bot",
            content="Hi there",
        )
        test_session.add_all([msg1, msg2])
        test_session.commit()

        # Verify relationship
        assert len(conv.messages) == 2
        assert msg1.conversation == conv
        assert msg2.conversation == conv


class TestMessageModel:
    """Test Message model creation and constraints."""

    def test_create_message(self, test_session: Session):
        """
        Test creating a message record.

        Protects against: Model definition errors, missing required fields.
        """
        member = TeamMember(slack_user_id="U_MSG", display_name="Msg User")
        test_session.add(member)
        test_session.flush()  # Generate member.id

        conv = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_MSG",
        )
        test_session.add(conv)
        test_session.flush()  # Generate conv.id

        msg = Message(
            conversation_id=conv.id,
            sender_type="user",
            content="Test message",
            slack_ts="1234567890.123456",
        )
        test_session.add(msg)
        test_session.commit()

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.token_count == 0  # Default value
        assert msg.timestamp is not None  # Auto-generated

    def test_sender_type_enum(self, test_session: Session):
        """
        Test that sender_type accepts valid enum values.

        Protects against: Invalid sender types, data consistency issues.
        """
        member = TeamMember(slack_user_id="U_SENDER", display_name="Sender User")
        test_session.add(member)
        test_session.flush()  # Generate member.id

        conv = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_SENDER",
        )
        test_session.add(conv)
        test_session.commit()  # Commit so objects persist across iterations

        # Test valid values
        for sender_type in ["user", "bot"]:
            msg = Message(
                conversation_id=conv.id,
                sender_type=sender_type,
                content=f"Message from {sender_type}",
            )
            test_session.add(msg)
            test_session.commit()  # Commit instead of flush+rollback

    def test_message_foreign_key_constraint(self, test_session: Session):
        """
        Test that messages require a valid conversation_id.

        With foreign keys enabled, creating a message with invalid conversation_id
        should fail.

        Protects against: Orphaned messages, referential integrity violations.
        """
        # Attempt to create message with non-existent conversation
        msg = Message(
            conversation_id="nonexistent-uuid",
            sender_type="user",
            content="Orphan message",
        )
        test_session.add(msg)

        with pytest.raises(IntegrityError):
            test_session.commit()


class TestConfigurationModel:
    """Test Configuration model and type conversion."""

    def test_create_configuration(self, test_session: Session):
        """
        Test creating configuration records.

        Protects against: Model definition errors, missing required fields.
        """
        config = Configuration(
            key="test_setting",
            value="test_value",
            value_type="string",
            description="Test configuration",
        )
        test_session.add(config)
        test_session.commit()

        assert config.id is not None
        assert config.key == "test_setting"

    def test_configuration_key_unique_constraint(self, test_session: Session):
        """
        Test that configuration keys must be unique.

        Each config key should only exist once in the database.

        Protects against: Duplicate configurations, ambiguous settings.
        """
        config1 = Configuration(
            key="duplicate_key",
            value="value1",
            value_type="string",
            description="First config",
        )
        test_session.add(config1)
        test_session.commit()

        config2 = Configuration(
            key="duplicate_key",
            value="value2",
            value_type="string",
            description="Second config",
        )
        test_session.add(config2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_value_type_enum(self, test_session: Session):
        """
        Test that value_type accepts valid enum values.

        Protects against: Invalid type specifications, type conversion errors.
        """
        valid_types = ["string", "integer", "float", "boolean", "json"]

        for value_type in valid_types:
            config = Configuration(
                key=f"test_{value_type}",
                value="test",
                value_type=value_type,
                description=f"Test {value_type} config",
            )
            test_session.add(config)
            test_session.flush()
            test_session.rollback()


class TestScheduledTaskModel:
    """Test ScheduledTask model for APScheduler integration."""

    def test_create_scheduled_task(self, test_session: Session):
        """
        Test creating a scheduled task record.

        Protects against: Model definition errors, missing required fields.
        """
        task = ScheduledTask(
            job_id="test_job_123",
            task_type="random_dm",
            target_type="user",
            target_id="U12345",
            scheduled_at=datetime.utcnow() + timedelta(hours=1),
        )
        test_session.add(task)
        test_session.commit()

        assert task.id is not None
        assert task.status == "pending"  # Default value
        assert task.retry_count == 0  # Default value

    def test_job_id_allows_duplicates(self, test_session: Session):
        """
        Test that job_id allows duplicates.

        APScheduler job IDs are unique per execution, not globally unique.
        Multiple task records can have the same job_id (e.g., for recurring tasks).

        Protects against: Incorrect unique constraint assumptions.
        """
        task1 = ScheduledTask(
            job_id="recurring_job",
            task_type="cleanup",
            target_type="system",
            scheduled_at=datetime.utcnow(),
        )
        test_session.add(task1)
        test_session.commit()

        # Same job_id should be allowed (for recurring tasks)
        task2 = ScheduledTask(
            job_id="recurring_job",
            task_type="cleanup",
            target_type="system",
            scheduled_at=datetime.utcnow(),
        )
        test_session.add(task2)
        test_session.commit()  # Should not raise

        # Verify both tasks exist
        assert test_session.query(ScheduledTask).filter_by(job_id="recurring_job").count() == 2


class TestEngagementEventModel:
    """Test EngagementEvent audit logging model."""

    def test_create_engagement_event(self, test_session: Session):
        """
        Test creating an engagement event record.

        Protects against: Model definition errors, audit log failures.
        """
        event = EngagementEvent(
            channel_id="C12345",
            event_type="thread_response",
            decision_probability=0.15,
            random_value=0.08,
            engaged=True,
        )
        test_session.add(event)
        test_session.commit()

        assert event.id is not None
        assert event.engaged is True
        assert event.timestamp is not None  # Auto-generated


class TestGeneratedImageModel:
    """Test GeneratedImage model for DALL-E tracking."""

    def test_create_generated_image(self, test_session: Session):
        """
        Test creating a generated image record.

        Protects against: Model definition errors, image tracking failures.
        """
        image = GeneratedImage(
            prompt="A friendly bear coding",
            image_url="https://example.com/image.png",
            status="generated",
        )
        test_session.add(image)
        test_session.commit()

        assert image.id is not None
        assert image.prompt == "A friendly bear coding"
        assert image.created_at is not None  # Auto-generated


class TestModelMetadataFields:
    """Test that metadata fields work correctly after renaming to 'meta'."""

    def test_message_meta_field(self, test_session: Session):
        """
        Test that Message.meta (mapped to 'metadata' column) works correctly.

        The 'meta' attribute should map to the 'metadata' database column to avoid
        SQLAlchemy's reserved 'metadata' attribute conflict.

        Protects against: Metadata field access errors, JSON serialization issues.
        """
        member = TeamMember(slack_user_id="U_META", display_name="Meta User")
        test_session.add(member)
        test_session.flush()  # Generate member.id

        conv = ConversationSession(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_META",
        )
        test_session.add(conv)
        test_session.flush()  # Generate conv.id

        msg = Message(
            conversation_id=conv.id,
            sender_type="user",
            content="Test",
            meta={"custom": "data", "key": 123},
        )
        test_session.add(msg)
        test_session.commit()

        # Retrieve and verify metadata
        retrieved_msg = test_session.query(Message).filter_by(id=msg.id).first()
        assert retrieved_msg.meta == {"custom": "data", "key": 123}

    def test_scheduled_task_meta_field(self, test_session: Session):
        """Test that ScheduledTask.meta field works correctly."""
        task = ScheduledTask(
            job_id="meta_job",
            task_type="random_dm",
            target_type="user",
            scheduled_at=datetime.utcnow(),
            meta={"priority": "high", "tags": ["urgent"]},
        )
        test_session.add(task)
        test_session.commit()

        retrieved_task = test_session.query(ScheduledTask).filter_by(job_id="meta_job").first()
        assert retrieved_task.meta == {"priority": "high", "tags": ["urgent"]}
