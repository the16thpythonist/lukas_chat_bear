"""
Slack Operations MCP Server.

Exposes Slack bot commands as MCP tools for LLM agent access.
Runs as separate process in same container, sharing codebase and database.

Uses official MCP Python SDK with SSE transport via Starlette/Uvicorn.
"""

import asyncio
import os
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn

from slack_sdk import WebClient

from src.services.command_service import CommandService
from src.utils.database import get_db_session
from src.utils.logger import logger


# Initialize MCP server
mcp_server = Server("slack-operations")

# Shared state
_db_session = None
_slack_client = None
_command_service = None


def get_service() -> CommandService:
    """Get or create CommandService instance."""
    global _db_session, _slack_client, _command_service

    if _command_service is None:
        logger.info("Initializing CommandService for MCP server...")
        _db_session = get_db_session()
        _slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

        # Initialize ImageService for this process
        # The MCP server runs as a separate process, so it needs its own ImageService instance
        from src.services import image_service as img_module
        from src.services.image_service import ImageService

        img_module.image_service = ImageService(
            db_session=_db_session,
            slack_client=_slack_client
        )
        logger.info("ImageService initialized for MCP server")

        _command_service = CommandService(_db_session, _slack_client)
        logger.info("CommandService initialized")

    return _command_service


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Slack operation tools."""
    return [
        Tool(
            name="post_message_to_channel",
            description=(
                "Post a message to a Slack channel as Lukas the Bear (the bot). "
                "Use this when the user asks to: send a message, post to a channel, "
                "share in a channel, announce something, or communicate to the team. "
                "The message will be posted as Lukas himself (not attributed to any user). "
                "Lukas has his own persona and will post messages directly as the bot."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message content to post to the channel (will be posted as Lukas the Bear)"
                    },
                    "channel": {
                        "type": "string",
                        "description": "Channel name (with or without #) or channel ID (e.g., 'general', '#general', or 'C123ABC456')"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional: Slack user ID for logging purposes only (not shown in the message)"
                    }
                },
                "required": ["message", "channel"]
            }
        ),

        Tool(
            name="create_reminder",
            description=(
                "Create a reminder for a user to be sent at a specific time. "
                "Use when the user asks to be reminded, pinged, notified, or alerted about something. "
                "Supports both duration-based reminders ('in 30 minutes', 'in 2 hours') and "
                "time-based reminders ('at 3pm', 'at 14:30'). "
                "The reminder will be sent as a direct message to the user."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What the user should be reminded about"
                    },
                    "when": {
                        "type": "string",
                        "description": (
                            "When to send the reminder. Supports durations like '30 minutes', '2 hours', "
                            "or specific times like '3pm', '14:30', '2:30pm'"
                        )
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Slack user ID of the person to remind (automatically provided from conversation context - use the ID from the system message)"
                    }
                },
                "required": ["task", "when", "user_id"]
            }
        ),

        Tool(
            name="get_team_info",
            description=(
                "Get information about the Slack workspace, bot status, or engagement statistics. "
                "Use when the user asks about: team members, who's on the team, "
                "bot configuration, bot status, settings, engagement metrics, or activity stats. "
                "Returns different types of information based on the requested type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["team", "status", "stats"],
                        "description": (
                            "'team' returns list of team members, "
                            "'status' returns bot configuration and settings, "
                            "'stats' returns engagement and activity statistics"
                        )
                    }
                },
                "required": ["info_type"]
            }
        ),

        Tool(
            name="update_bot_config",
            description=(
                "Update bot configuration settings. **ADMIN ONLY - requires admin privileges.** "
                "Use when an admin asks to change bot behavior, intervals, probabilities, or settings. "
                "Will return an error if the user is not an admin. "
                "Settings include DM interval, thread response probability, and image posting frequency."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "setting": {
                        "type": "string",
                        "enum": ["dm_interval", "thread_probability", "image_interval"],
                        "description": (
                            "'dm_interval' controls how often random DMs are sent, "
                            "'thread_probability' controls likelihood of responding in threads, "
                            "'image_interval' controls how often images are auto-posted"
                        )
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "New value for the setting. Examples: '24 hours', '0.30' (for probability), '7 days'"
                        )
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Slack user ID of the admin making the change (automatically provided from conversation context - use the ID from the system message)"
                    }
                },
                "required": ["setting", "value", "user_id"]
            }
        ),

        Tool(
            name="generate_and_post_image",
            description=(
                "Generate an AI-created bear image using DALL-E and post it to a Slack channel. "
                "**ADMIN ONLY - requires admin privileges.** "
                "Use when an admin asks to: create an image, generate a picture, "
                "post art, make an image, or share AI-generated content. "
                "Will return an error if the user is not an admin."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "Optional theme or description for the image (e.g., 'halloween', 'winter', 'coding'). Defaults to seasonal theme if not provided."
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional channel to post the image to. If not provided, uses the current channel."
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Slack user ID of the admin requesting the image (automatically provided from conversation context - use the ID from the system message)"
                    }
                },
                "required": ["user_id"]
            }
        ),

        Tool(
            name="schedule_channel_message",
            description=(
                "Schedule a one-time message to be posted to a Slack channel at a future time. "
                "**ADMIN ONLY - requires admin privileges.** "
                "Use when an admin asks to: schedule a message, remind the channel, "
                "post something later, send a message at a specific time, or set up an announcement. "
                "Supports natural language time expressions like 'in 2 hours', '3pm Friday', 'tomorrow at 2pm', etc. "
                "Will return an error if the user is not an admin."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message content to post to the channel at the scheduled time"
                    },
                    "channel": {
                        "type": "string",
                        "description": "Channel name (with or without #) or channel ID where the message will be posted"
                    },
                    "when": {
                        "type": "string",
                        "description": (
                            "When to post the message. Supports natural language like "
                            "'in 2 hours', '3pm Friday', 'tomorrow at 2pm', 'next Monday at 10am', etc."
                        )
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Slack user ID of the admin scheduling the message (automatically provided from conversation context - use the ID from the system message)"
                    }
                },
                "required": ["message", "channel", "when", "user_id"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a Slack operation tool."""
    logger.info(f"MCP tool called: {name} with arguments: {arguments}")

    service = get_service()

    try:
        if name == "post_message_to_channel":
            result = await service.post_message(
                message=arguments["message"],
                channel=arguments["channel"],
                user_id=arguments.get("user_id")  # Optional - for logging only
            )

        elif name == "create_reminder":
            result = await service.create_reminder(
                task=arguments["task"],
                when=arguments["when"],
                user_id=arguments["user_id"]
            )

        elif name == "get_team_info":
            result = await service.get_info(
                info_type=arguments["info_type"]
            )

        elif name == "update_bot_config":
            result = await service.update_config(
                setting=arguments["setting"],
                value=arguments["value"],
                user_id=arguments["user_id"]
            )

        elif name == "generate_and_post_image":
            result = await service.generate_image(
                theme=arguments.get("theme"),
                channel=arguments.get("channel"),
                user_id=arguments["user_id"]
            )

        elif name == "schedule_channel_message":
            result = await service.schedule_message(
                message=arguments["message"],
                channel=arguments["channel"],
                when=arguments["when"],
                user_id=arguments["user_id"]
            )

        else:
            result = {
                "success": False,
                "message": f"Unknown tool: {name}"
            }

        # Format response for MCP client
        # Use formatted string if available, otherwise use message
        if result.get("success"):
            response_text = result.get("formatted") or result.get("message", str(result))
            # Add success emoji
            if not response_text.startswith("✅") and not response_text.startswith("⏰") and not response_text.startswith("🐻"):
                response_text = f"✅ {response_text} 🐻"
        else:
            error_msg = result.get("message") or result.get("error", "Unknown error")
            response_text = f"❌ {error_msg} 🐻"

        logger.info(f"MCP tool {name} result: success={result.get('success')}")

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Error executing MCP tool {name}: {e}", exc_info=True)
        error_text = f"❌ Error executing {name}: {str(e)} 🐻"
        return [TextContent(type="text", text=error_text)]


# Create SSE transport
sse = SseServerTransport("/messages/")


async def handle_sse(request):
    """
    Handle SSE connection for MCP communication.

    This endpoint establishes a Server-Sent Events stream for
    server-to-client communication.
    """
    logger.info("New SSE connection established")

    try:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Error in SSE connection: {e}", exc_info=True)
    finally:
        logger.info("SSE connection closed")

    return Response()


# Create Starlette ASGI application
app = Starlette(
    debug=os.getenv("DEBUG", "false").lower() == "true",
    routes=[
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)


def main():
    """Run the MCP server."""
    port = int(os.getenv("MCP_SLACK_OPS_PORT", "9766"))
    host = os.getenv("MCP_SLACK_OPS_HOST", "0.0.0.0")

    logger.info("=" * 60)
    logger.info("🚀 Starting Slack Operations MCP Server")
    logger.info(f"📡 Host: {host}")
    logger.info(f"🔌 Port: {port}")
    logger.info(f"🔗 SSE Endpoint: http://{host}:{port}/sse")
    logger.info(f"📬 Messages Endpoint: http://{host}:{port}/messages/")
    logger.info("=" * 60)

    # Run uvicorn server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
