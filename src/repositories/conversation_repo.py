"""
Conversation repository.

Data access layer for ConversationSession and Message entities.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session, joinedload

from src.models.conversation import ConversationSession
from src.models.message import Message
from src.utils.logger import logger


class ConversationRepository:
    """Repository for conversation-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_conversation(
        self,
        team_member_id: str,
        channel_type: str,
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> ConversationSession:
        """
        Create a new conversation session.

        Args:
            team_member_id: ID of the team member
            channel_type: Type of channel (dm, channel, thread)
            channel_id: Slack channel ID (if applicable)
            thread_ts: Slack thread timestamp (if applicable)

        Returns:
            Created ConversationSession
        """
        conversation = ConversationSession(
            team_member_id=team_member_id,
            channel_type=channel_type,
            channel_id=channel_id,
            thread_ts=thread_ts,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info(f"Created conversation {conversation.id} for team member {team_member_id}")
        return conversation

    def get_active_conversation(
        self,
        team_member_id: str,
        channel_type: str,
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> Optional[ConversationSession]:
        """
        Get active conversation for a team member in a specific context.

        Args:
            team_member_id: ID of the team member
            channel_type: Type of channel
            channel_id: Slack channel ID (if applicable)
            thread_ts: Slack thread timestamp (if applicable)

        Returns:
            Active ConversationSession or None
        """
        query = self.db.query(ConversationSession).filter(
            and_(
                ConversationSession.team_member_id == team_member_id,
                ConversationSession.channel_type == channel_type,
                ConversationSession.is_active == True,
            )
        )

        if channel_id:
            query = query.filter(ConversationSession.channel_id == channel_id)
        if thread_ts:
            query = query.filter(ConversationSession.thread_ts == thread_ts)

        return query.first()

    def get_or_create_conversation(
        self,
        team_member_id: str,
        channel_type: str,
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> ConversationSession:
        """
        Get existing active conversation or create a new one.

        Args:
            team_member_id: ID of the team member
            channel_type: Type of channel
            channel_id: Slack channel ID
            thread_ts: Slack thread timestamp

        Returns:
            ConversationSession (existing or new)
        """
        conversation = self.get_active_conversation(
            team_member_id, channel_type, channel_id, thread_ts
        )
        if conversation:
            return conversation

        return self.create_conversation(
            team_member_id, channel_type, channel_id, thread_ts
        )

    def add_message(
        self,
        conversation_id: str,
        sender_type: str,
        content: str,
        slack_ts: Optional[str] = None,
        token_count: int = 0,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Add a message to a conversation.

        Args:
            conversation_id: ID of the conversation
            sender_type: Type of sender (user or bot)
            content: Message content
            slack_ts: Slack message timestamp
            token_count: Estimated token count
            metadata: Additional message metadata

        Returns:
            Created Message
        """
        message = Message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            content=content,
            slack_ts=slack_ts,
            token_count=token_count,
            meta=metadata,  # Use 'meta' attribute (maps to 'metadata' column)
        )
        self.db.add(message)

        # Update conversation metadata
        conversation = self.db.query(ConversationSession).get(conversation_id)
        if conversation:
            conversation.last_message_at = datetime.utcnow()
            conversation.message_count += 1
            conversation.total_tokens += token_count

        self.db.commit()
        self.db.refresh(message)
        logger.debug(f"Added message {message.id} to conversation {conversation_id}")
        return message

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[Message]:
        """
        Get recent messages from a conversation.

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages to return

        Returns:
            List of Message objects (ordered oldest to newest)
        """
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(desc(Message.timestamp))
            .limit(limit)
            .all()
        )
        # Reverse to get oldest to newest
        return list(reversed(messages))

    def deactivate_old_conversations(self, hours: int = 24) -> int:
        """
        Deactivate conversations with no activity in the specified hours.

        Args:
            hours: Number of hours of inactivity

        Returns:
            Number of conversations deactivated
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = (
            self.db.query(ConversationSession)
            .filter(
                and_(
                    ConversationSession.is_active == True,
                    ConversationSession.last_message_at < cutoff_time,
                )
            )
            .update({"is_active": False})
        )
        self.db.commit()
        logger.info(f"Deactivated {result} conversations older than {hours} hours")
        return result

    def delete_old_conversations(self, days: int = 90) -> int:
        """
        Delete conversations older than specified days.

        Args:
            days: Retention period in days

        Returns:
            Number of conversations deleted
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        conversations = (
            self.db.query(ConversationSession)
            .filter(ConversationSession.created_at < cutoff_time)
            .all()
        )
        count = len(conversations)
        for conv in conversations:
            self.db.delete(conv)
        self.db.commit()
        logger.info(f"Deleted {count} conversations older than {days} days")
        return count
