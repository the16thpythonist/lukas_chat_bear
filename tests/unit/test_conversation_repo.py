"""
Tests for ConversationRepository.

Tests conversation management operations including creation, message tracking,
and cleanup operations.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.models import TeamMember, ConversationSession, Message
from src.repositories.conversation_repo import ConversationRepository


class TestConversationCreation:
    """Test conversation creation operations."""

    def test_create_conversation(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test creating a new conversation.

        Protects against: Conversation creation failures, missing required fields.
        """
        # Create team member first
        member = TeamMember(slack_user_id="U_CREATE", display_name="Create User")
        test_session.add(member)
        test_session.flush()

        # Create conversation
        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C12345",
        )

        assert conv.id is not None
        assert conv.team_member_id == member.id
        assert conv.channel_type == "dm"
        assert conv.channel_id == "C12345"
        assert conv.is_active is True
        assert conv.message_count == 0

    def test_create_conversation_with_thread(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test creating a conversation in a thread context.

        Thread conversations include thread_ts parameter for Slack threading.

        Protects against: Thread context tracking failures.
        """
        member = TeamMember(slack_user_id="U_THREAD", display_name="Thread User")
        test_session.add(member)
        test_session.flush()

        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="thread",
            channel_id="C_THREAD",
            thread_ts="1234567890.123456",
        )

        assert conv.channel_type == "thread"
        assert conv.thread_ts == "1234567890.123456"


class TestConversationRetrieval:
    """Test conversation query operations."""

    def test_get_active_conversation_dm(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test retrieving an active DM conversation.

        The seeded database has pre-created conversations, so this tests that
        get_active_conversation correctly filters by team member and channel type.

        Protects against: Query logic errors, incorrect conversation retrieval.
        """
        # Get admin user from seeded database
        admin = seeded_db.query(TeamMember).filter_by(slack_user_id="U001_ADMIN").first()
        assert admin is not None

        # Should find the existing DM conversation
        conv = conversation_repo.get_active_conversation(
            team_member_id=admin.id,
            channel_type="dm",
            channel_id="C001",
        )

        assert conv is not None
        assert conv.team_member_id == admin.id
        assert conv.channel_type == "dm"
        assert conv.is_active is True

    def test_get_active_conversation_not_found(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test get_active_conversation returns None when no match exists.

        Protects against: Incorrect default behavior, exception on missing data.
        """
        admin = seeded_db.query(TeamMember).filter_by(slack_user_id="U001_ADMIN").first()

        # Query for non-existent channel
        conv = conversation_repo.get_active_conversation(
            team_member_id=admin.id,
            channel_type="dm",
            channel_id="C_NONEXISTENT",
        )

        assert conv is None

    def test_get_active_conversation_with_thread_ts(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test retrieving conversation by thread_ts.

        Thread timestamp must match exactly for correct conversation retrieval.

        Protects against: Thread context mixing, incorrect message threading.
        """
        regular_user = seeded_db.query(TeamMember).filter_by(slack_user_id="U003_REGULAR").first()

        # Should find conversation with specific thread_ts
        conv = conversation_repo.get_active_conversation(
            team_member_id=regular_user.id,
            channel_type="channel",
            channel_id="C002",
            thread_ts="1234567890.123456",
        )

        assert conv is not None
        assert conv.thread_ts == "1234567890.123456"

    def test_get_or_create_conversation_existing(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test get_or_create returns existing conversation when found.

        Should NOT create a duplicate conversation if one already exists.

        Protects against: Duplicate conversation creation, data fragmentation.
        """
        admin = seeded_db.query(TeamMember).filter_by(slack_user_id="U001_ADMIN").first()

        # Get conversation count before
        count_before = seeded_db.query(ConversationSession).count()

        conv = conversation_repo.get_or_create_conversation(
            team_member_id=admin.id,
            channel_type="dm",
            channel_id="C001",
        )

        # Should return existing conversation without creating new one
        count_after = seeded_db.query(ConversationSession).count()
        assert count_before == count_after
        assert conv is not None
        assert conv.channel_id == "C001"

    def test_get_or_create_conversation_creates_new(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test get_or_create creates new conversation when none exists.

        Idempotency: Should create exactly one new conversation.

        Protects against: Creation failures, unexpected multiple records.
        """
        admin = seeded_db.query(TeamMember).filter_by(slack_user_id="U001_ADMIN").first()

        count_before = seeded_db.query(ConversationSession).count()

        # Create conversation for new channel
        conv = conversation_repo.get_or_create_conversation(
            team_member_id=admin.id,
            channel_type="dm",
            channel_id="C_NEW_CHANNEL",
        )

        count_after = seeded_db.query(ConversationSession).count()
        assert count_after == count_before + 1
        assert conv.channel_id == "C_NEW_CHANNEL"


class TestMessageOperations:
    """Test message creation and retrieval operations."""

    def test_add_message(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test adding a message to a conversation.

        Should create message and update conversation metadata (message_count, total_tokens).

        Protects against: Message creation failures, metadata update failures.
        """
        # Setup conversation
        member = TeamMember(slack_user_id="U_MSG", display_name="Msg User")
        test_session.add(member)
        test_session.flush()

        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_MSG",
        )

        # Add message
        msg = conversation_repo.add_message(
            conversation_id=conv.id,
            sender_type="user",
            content="Hello Lukas!",
            slack_ts="1234567890.111111",
            token_count=5,
        )

        assert msg.id is not None
        assert msg.content == "Hello Lukas!"
        assert msg.token_count == 5

        # Verify conversation metadata was updated
        test_session.refresh(conv)
        assert conv.message_count == 1
        assert conv.total_tokens == 5
        assert conv.last_message_at is not None

    def test_add_multiple_messages_updates_metadata(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test that adding multiple messages correctly accumulates counts.

        Message count and token count should increment with each message.

        Protects against: Incorrect accumulation, metadata sync issues.
        """
        member = TeamMember(slack_user_id="U_MULTI", display_name="Multi User")
        test_session.add(member)
        test_session.flush()

        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_MULTI",
        )

        # Add three messages
        conversation_repo.add_message(conv.id, "user", "Message 1", token_count=10)
        conversation_repo.add_message(conv.id, "bot", "Message 2", token_count=15)
        conversation_repo.add_message(conv.id, "user", "Message 3", token_count=8)

        # Verify cumulative counts
        test_session.refresh(conv)
        assert conv.message_count == 3
        assert conv.total_tokens == 33  # 10 + 15 + 8

    def test_add_message_with_metadata_parameter(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test adding a message with metadata parameter.

        NOTE: The repository uses 'metadata' parameter but model uses 'meta' attribute.
        This test verifies the parameter mapping works correctly.

        Protects against: Metadata field mapping errors, JSON serialization issues.
        """
        member = TeamMember(slack_user_id="U_META_MSG", display_name="Meta User")
        test_session.add(member)
        test_session.flush()

        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_META",
        )

        # Add message with metadata
        msg = conversation_repo.add_message(
            conversation_id=conv.id,
            sender_type="user",
            content="Test",
            metadata={"source": "web", "priority": "high"},
        )

        # Retrieve and verify (model uses 'meta' attribute)
        test_session.refresh(msg)
        assert msg.meta == {"source": "web", "priority": "high"}

    def test_get_recent_messages(self, seeded_db: Session, conversation_repo: ConversationRepository):
        """
        Test retrieving recent messages from a conversation.

        Messages should be returned in chronological order (oldest to newest).

        Protects against: Incorrect ordering, pagination failures.
        """
        admin = seeded_db.query(TeamMember).filter_by(slack_user_id="U001_ADMIN").first()
        conv = seeded_db.query(ConversationSession).filter_by(
            team_member_id=admin.id,
            channel_type="dm"
        ).first()

        messages = conversation_repo.get_recent_messages(conv.id, limit=10)

        # Should return messages in chronological order
        assert len(messages) == 2  # Seeded data has 2 messages for admin's DM
        assert messages[0].timestamp <= messages[1].timestamp

    def test_get_recent_messages_respects_limit(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test that get_recent_messages respects the limit parameter.

        Should return at most 'limit' messages, even if more exist.

        Protects against: Memory issues from loading too many messages, pagination errors.
        """
        member = TeamMember(slack_user_id="U_LIMIT", display_name="Limit User")
        test_session.add(member)
        test_session.flush()

        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_LIMIT",
        )

        # Add 10 messages
        for i in range(10):
            conversation_repo.add_message(
                conv.id,
                "user",
                f"Message {i}",
                token_count=5,
            )

        # Request only 3 most recent
        messages = conversation_repo.get_recent_messages(conv.id, limit=3)

        assert len(messages) == 3


class TestConversationCleanup:
    """Test conversation cleanup and maintenance operations."""

    def test_deactivate_old_conversations(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test deactivating conversations with no recent activity.

        Conversations inactive for specified hours should be marked as inactive.

        Protects against: Stale conversation accumulation, context window pollution.
        """
        member = TeamMember(slack_user_id="U_DEACTIVATE", display_name="Deactivate User")
        test_session.add(member)
        test_session.flush()

        # Create two conversations: one recent, one old
        recent_conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_RECENT",
        )
        recent_conv.last_message_at = datetime.utcnow() - timedelta(hours=12)

        old_conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_OLD",
        )
        old_conv.last_message_at = datetime.utcnow() - timedelta(hours=48)

        test_session.commit()

        # Deactivate conversations older than 24 hours
        count = conversation_repo.deactivate_old_conversations(hours=24)

        assert count == 1  # Only old_conv should be deactivated

        # Verify status
        test_session.refresh(recent_conv)
        test_session.refresh(old_conv)
        assert recent_conv.is_active is True
        assert old_conv.is_active is False

    def test_deactivate_old_conversations_none_matching(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test deactivating when no conversations match the criteria.

        Should return 0 without errors.

        Protects against: Errors when no data matches cleanup criteria.
        """
        member = TeamMember(slack_user_id="U_NONE", display_name="None User")
        test_session.add(member)
        test_session.flush()

        # Create recent conversation
        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_NONE",
        )
        conv.last_message_at = datetime.utcnow()
        test_session.commit()

        # Try to deactivate old conversations (none should match)
        count = conversation_repo.deactivate_old_conversations(hours=1)

        assert count == 0
        test_session.refresh(conv)
        assert conv.is_active is True

    def test_delete_old_conversations(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test deleting conversations older than specified days.

        Old conversations should be permanently deleted from database.

        Protects against: Database bloat, retention policy violations.
        """
        member = TeamMember(slack_user_id="U_DELETE", display_name="Delete User")
        test_session.add(member)
        test_session.flush()

        # Create two conversations with different ages
        recent_conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_RECENT_DEL",
        )
        recent_conv.created_at = datetime.utcnow() - timedelta(days=30)

        old_conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_OLD_DEL",
        )
        old_conv.created_at = datetime.utcnow() - timedelta(days=120)

        test_session.commit()

        # Delete conversations older than 90 days
        count = conversation_repo.delete_old_conversations(days=90)

        assert count == 1  # Only old_conv should be deleted

        # Verify deletion
        assert test_session.query(ConversationSession).get(recent_conv.id) is not None
        assert test_session.query(ConversationSession).get(old_conv.id) is None

    def test_delete_old_conversations_cascades_to_messages(self, test_session: Session, conversation_repo: ConversationRepository):
        """
        Test that deleting a conversation also deletes its messages.

        Foreign key cascade should remove all messages when conversation is deleted.

        Protects against: Orphaned messages, referential integrity violations.
        """
        member = TeamMember(slack_user_id="U_CASCADE", display_name="Cascade User")
        test_session.add(member)
        test_session.flush()

        # Create old conversation with messages
        conv = conversation_repo.create_conversation(
            team_member_id=member.id,
            channel_type="dm",
            channel_id="C_CASCADE",
        )
        conv.created_at = datetime.utcnow() - timedelta(days=100)
        test_session.commit()

        # Add messages
        msg1 = conversation_repo.add_message(conv.id, "user", "Message 1")
        msg2 = conversation_repo.add_message(conv.id, "bot", "Message 2")

        # Delete old conversations
        conversation_repo.delete_old_conversations(days=90)

        # Verify both conversation and messages are deleted
        assert test_session.query(ConversationSession).get(conv.id) is None
        assert test_session.query(Message).get(msg1.id) is None
        assert test_session.query(Message).get(msg2.id) is None
