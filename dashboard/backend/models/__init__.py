"""
Database models for dashboard backend.
Imports existing models from the bot's src/models/ directory.

Note: Dashboard uses the same SQLAlchemy models as the bot.
No duplication needed - we share the database schema.
"""

# Import models from bot's src/models
# These models are already defined and maintained by the bot
try:
    from src.models.message import Message
    from src.models.conversation import ConversationSession as Conversation
    from src.models.generated_image import GeneratedImage
    from src.models.scheduled_task import ScheduledTask
    from src.models.team_member import TeamMember
    from src.models.config import Configuration

    __all__ = [
        'Message',
        'Conversation',
        'GeneratedImage',
        'ScheduledTask',
        'TeamMember',
        'Configuration'
    ]

except ImportError as e:
    # Models not yet available (bot models may not be implemented yet)
    import warnings
    warnings.warn(
        f"Could not import bot models: {e}. "
        "Dashboard will not be able to query the database until bot models are available."
    )

    # Define placeholder classes for development
    class Message:
        """Placeholder for Message model."""
        pass

    class Conversation:
        """Placeholder for Conversation model."""
        pass

    class GeneratedImage:
        """Placeholder for GeneratedImage model."""
        pass

    class ScheduledTask:
        """Placeholder for ScheduledTask model."""
        pass

    class TeamMember:
        """Placeholder for TeamMember model."""
        pass

    class Configuration:
        """Placeholder for Configuration model."""
        pass

    __all__ = [
        'Message',
        'Conversation',
        'GeneratedImage',
        'ScheduledTask',
        'TeamMember',
        'Configuration'
    ]
