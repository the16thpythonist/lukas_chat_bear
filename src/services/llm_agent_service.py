"""
LLM Agent service with MCP tool integration using official MCP Python SDK.

Uses the official MCP SDK with SSE transport to connect to MCP servers
running in Docker containers. Integrates with LangChain for agent capabilities.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from pybreaker import CircuitBreaker
from pydantic import BaseModel, Field, create_model

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from src.models.message import Message
from src.services.persona_service import persona_service
from src.utils.logger import logger
from src.utils.retry import retry_on_api_error


class LLMAgentService:
    """
    Agent-based LLM service with MCP tool access via SSE.

    Features:
    - Connects to MCP servers via SSE (Server-Sent Events)
    - Official MCP Python SDK for protocol compliance
    - Autonomous tool selection via LangChain
    - Maintains Lukas the Bear personality
    - Circuit breaker for fault tolerance
    - Graceful degradation
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_context_messages: int = 10,
        max_tokens_per_request: int = 8000,
        max_response_tokens: int = 8000,  # Increased for reasoning models
    ):
        """
        Initialize LLM agent service.

        Args:
            model: LLM model name (defaults to env LLM_MODEL or gpt-4o-mini)
            max_context_messages: Maximum message pairs in context
            max_tokens_per_request: Maximum tokens per request
            max_response_tokens: Maximum tokens in response
        """
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.max_context_messages = max_context_messages
        self.max_tokens_per_request = max_tokens_per_request
        self.max_response_tokens = max_response_tokens

        # Initialize OpenAI LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            raise ValueError("OPENAI_API_KEY is required")

        self.llm = ChatOpenAI(
            model=self.model,
            temperature=0.7,
            max_tokens=self.max_response_tokens,
            api_key=api_key
        )

        # MCP connection management (support multiple servers)
        self.mcp_sessions: Dict[str, ClientSession] = {}  # server_name -> session
        self.mcp_tools: List[StructuredTool] = []
        self.agent = None  # LangGraph agent
        self._mcp_tasks: List[asyncio.Task] = []  # Background tasks for MCP lifecycle
        self._mcp_ready_events: List[asyncio.Event] = []  # Signals when each MCP is ready

        # Circuit breaker for MCP connections
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,
            reset_timeout=60,
        )

        logger.info(f"LLM Agent service initialized with model {self.model}")

    async def _mcp_connection_lifecycle(self, url: str, server_name: str, ready_event: asyncio.Event) -> None:
        """
        Background task that manages MCP connection lifecycle for a specific server.

        Keeps the SSE context manager alive throughout bot lifetime.
        This prevents the "exit cancel scope in different task" error.

        Args:
            url: MCP server URL
            server_name: Name of the MCP server (for logging and tracking)
            ready_event: Event to signal when this server is ready
        """
        try:
            logger.info(f"Starting MCP connection to {server_name} at {url}...")

            # Enter SSE context with increased timeouts
            # timeout: Connection establishment timeout (increased from 5s to 30s)
            # sse_read_timeout: Maximum idle time on SSE stream (increased from 300s to 3600s = 1 hour)
            async with sse_client(
                url=url,
                timeout=30.0,           # 30 seconds to establish connection
                sse_read_timeout=3600.0  # 1 hour idle timeout for SSE stream
            ) as (read_stream, write_stream):
                # Enter MCP session context
                async with ClientSession(read_stream, write_stream) as session:
                    self.mcp_sessions[server_name] = session

                    # Initialize session
                    await session.initialize()
                    logger.info(f"{server_name} MCP session initialized successfully")

                    # List and register tools
                    tools_list = await session.list_tools()
                    logger.info(f"Found {len(tools_list.tools)} tools from {server_name}")

                    # Add tools to global list
                    for mcp_tool in tools_list.tools:
                        langchain_tool = self._create_langchain_tool(mcp_tool, server_name)
                        self.mcp_tools.append(langchain_tool)
                        logger.info(f"  [{server_name}] {mcp_tool.name}: {mcp_tool.description}")

                    logger.info(f"{server_name} registered {len(tools_list.tools)} tools")

                    # Signal that this MCP server is ready
                    ready_event.set()

                    # Keep connection alive indefinitely
                    # This task will run until cancelled (bot shutdown)
                    try:
                        await asyncio.Event().wait()  # Wait forever
                    except asyncio.CancelledError:
                        logger.info(f"{server_name} MCP connection lifecycle task cancelled")
                        raise

        except httpx.ReadTimeout as e:
            # Expected timeout on idle SSE connection - this is non-critical
            # With 1-hour read timeout, this should rarely happen during normal operation
            logger.debug(f"{server_name} MCP SSE connection timed out (expected for idle connections): {e}")
            ready_event.set()  # Tools are already registered, this is fine
        except asyncio.CancelledError:
            # Expected during bot shutdown
            logger.info(f"{server_name} MCP connection cancelled during shutdown")
            ready_event.set()
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            # Log connection errors but don't fail - agent will work without this MCP server
            logger.warning(f"{server_name} MCP connection error: {e}")
            logger.debug(f"Full {server_name} error details:", exc_info=True)
            logger.info(f"Agent will continue without {server_name} tools")
            ready_event.set()  # Unblock initialization even on error

    async def initialize_mcp(self) -> None:
        """
        Initialize MCP clients with SSE transport in background tasks.

        Connects to multiple MCP servers:
        - web-search-mcp: Web search capabilities
        - slack-operations-mcp: Slack command operations

        Creates long-lived background tasks that maintain MCP connections.
        This prevents async context cleanup errors by keeping context managers
        alive in the same task where they were created.
        """
        # Configure MCP servers to connect to
        mcp_servers = []

        web_search_url = os.getenv("MCP_WEB_SEARCH_URL")
        if web_search_url:
            mcp_servers.append(("web-search", web_search_url))

        slack_ops_url = os.getenv("MCP_SLACK_OPS_URL")
        if slack_ops_url:
            mcp_servers.append(("slack-operations", slack_ops_url))

        if not mcp_servers:
            logger.warning("No MCP servers configured, agent will run without MCP tools")
            return

        try:
            logger.info(f"Initializing {len(mcp_servers)} MCP server(s)...")

            # Create background task for each MCP server
            for server_name, server_url in mcp_servers:
                ready_event = asyncio.Event()
                self._mcp_ready_events.append(ready_event)

                task = asyncio.create_task(
                    self._mcp_connection_lifecycle(server_url, server_name, ready_event)
                )
                self._mcp_tasks.append(task)

            # Wait for all MCP servers to be ready (with timeout)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[event.wait() for event in self._mcp_ready_events]),
                    timeout=30.0
                )

                # Create agent with all tools from all servers
                if self.mcp_tools:
                    self._create_agent()
                    logger.info(f"MCP initialization complete: {len(self.mcp_tools)} total tools from {len(mcp_servers)} server(s)")
                else:
                    logger.warning("MCP initialization completed but no tools registered")

            except asyncio.TimeoutError:
                logger.error("MCP initialization timed out after 30s")
                # Cancel all tasks
                for task in self._mcp_tasks:
                    task.cancel()

        except Exception as e:
            logger.error(f"Failed to initialize MCP: {e}", exc_info=True)

    def _create_pydantic_model_from_schema(self, tool_name: str, input_schema: dict) -> type[BaseModel]:
        """
        Create a Pydantic model from MCP tool input schema.

        Args:
            tool_name: Name of the tool
            input_schema: JSON Schema for tool inputs

        Returns:
            Pydantic model class
        """
        # MCP uses JSON Schema format
        properties = input_schema.get('properties', {})
        required = input_schema.get('required', [])

        # Build Pydantic field definitions
        field_definitions = {}
        for field_name, field_info in properties.items():
            field_type = str  # Default to string
            field_description = field_info.get('description', '')

            # Determine Python type from JSON schema type
            json_type = field_info.get('type', 'string')
            if json_type == 'number' or json_type == 'integer':
                field_type = int
            elif json_type == 'boolean':
                field_type = bool

            # Create Field with description and optional/required
            if field_name in required:
                field_definitions[field_name] = (field_type, Field(description=field_description))
            else:
                field_definitions[field_name] = (Optional[field_type], Field(default=None, description=field_description))

        # Create dynamic Pydantic model
        model_name = f"{tool_name.replace('-', '_').title()}Args"
        return create_model(model_name, **field_definitions)

    def _create_langchain_tool(self, mcp_tool, server_name: str) -> StructuredTool:
        """
        Convert an MCP tool to a LangChain tool with proper schema.

        Args:
            mcp_tool: MCP tool definition
            server_name: Name of the MCP server providing this tool

        Returns:
            LangChain StructuredTool wrapper
        """
        # Create Pydantic model from MCP input schema
        args_schema = None
        if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
            try:
                args_schema = self._create_pydantic_model_from_schema(
                    mcp_tool.name,
                    mcp_tool.inputSchema
                )
                logger.debug(f"Created Pydantic schema for tool '{mcp_tool.name}': {args_schema}")
            except Exception as e:
                logger.warning(f"Failed to create schema for tool '{mcp_tool.name}': {e}")

        async def tool_func(**kwargs) -> str:
            """Execute the MCP tool."""
            try:
                logger.debug(f"Calling MCP tool '{mcp_tool.name}' from {server_name} with arguments: {kwargs}")

                # Get the session for this server
                session = self.mcp_sessions.get(server_name)
                if not session:
                    logger.error(f"No MCP session found for server '{server_name}'")
                    return f"Error: MCP server '{server_name}' not connected"

                result = await session.call_tool(
                    name=mcp_tool.name,
                    arguments=kwargs
                )

                logger.debug(f"MCP tool '{mcp_tool.name}' returned: {type(result)}")

                # Extract text content from result
                if hasattr(result, 'content') and result.content:
                    if isinstance(result.content, list):
                        # Concatenate all text content
                        text_parts = []
                        for item in result.content:
                            if hasattr(item, 'text'):
                                text_parts.append(str(item.text))
                            else:
                                text_parts.append(str(item))
                        return "\n".join(text_parts)
                    elif hasattr(result.content, 'text'):
                        return result.content.text

                return str(result)

            except Exception as e:
                logger.error(f"Error calling MCP tool {mcp_tool.name}: {e}", exc_info=True)
                return f"Error: {str(e)}"

        # Create LangChain StructuredTool with proper schema
        return StructuredTool.from_function(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
            coroutine=tool_func,
            args_schema=args_schema,  # Provide the Pydantic model
        )

    def _create_agent(self):
        """Create LangGraph agent with MCP tools."""
        if not self.mcp_tools:
            logger.warning("No MCP tools available, skipping agent creation")
            return

        # Get system prompt
        system_prompt = persona_service.get_system_prompt()
        system_message = system_prompt + "\n\nYou have access to tools. Use them when they would be helpful to answer the user's question."

        # Create react agent with tools
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.mcp_tools,
            prompt=SystemMessage(content=system_message)
        )

        logger.info("LangGraph agent created with MCP tools")

    def _build_conversation_context(
        self,
        conversation_messages: List[Message]
    ) -> List:
        """
        Build conversation history for agent.

        Args:
            conversation_messages: Previous messages in conversation

        Returns:
            List of LangChain message objects
        """
        messages = []

        # Add recent conversation history (sliding window)
        for msg in conversation_messages[-self.max_context_messages * 2:]:
            if msg.sender_type == "bot":
                messages.append(AIMessage(content=msg.content))
            else:
                messages.append(HumanMessage(content=msg.content))

        return messages

    @retry_on_api_error(max_attempts=3, min_wait=1, max_wait=10)
    async def _call_agent(
        self,
        user_message: str,
        chat_history: List = None,
        use_tools: bool = True,
        user_context: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Call agent or LLM with circuit breaker protection.

        Args:
            user_message: User's message text
            chat_history: Previous conversation messages
            use_tools: Whether to enable tool use
            user_context: Optional dict with user_id and user_name for tool calls

        Returns:
            AI response text
        """
        try:
            if use_tools and self.agent:
                # Use LangGraph agent with tools
                messages = chat_history or []

                # Inject user context as system message if provided
                if user_context:
                    context_msg = (
                        f"\n\nCurrent conversation context:\n"
                        f"- User: {user_context['user_name']}\n"
                        f"- Slack User ID: {user_context['user_id']}\n\n"
                        f"IMPORTANT: When using tools that require 'user_id' parameter "
                        f"(like generate_and_post_image, update_bot_config, create_reminder), "
                        f"use the Slack User ID provided above. DO NOT ask the user for their ID."
                    )
                    messages.insert(0, SystemMessage(content=context_msg))

                messages.append(HumanMessage(content=user_message))

                logger.info(f"Calling agent with {len(messages)} messages, use_tools={use_tools}")
                if user_context:
                    logger.info(f"User context: {user_context['user_name']} ({user_context['user_id']})")
                logger.info(f"User message: {user_message[:100]}...")

                result = await self.agent.ainvoke({"messages": messages})

                logger.info(f"Agent returned result type: {type(result)}")
                logger.info(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")

                # Extract the final message from the result
                if isinstance(result, dict) and "messages" in result:
                    logger.info(f"Result has {len(result['messages'])} messages")
                    final_message = result["messages"][-1]
                    logger.info(f"Final message type: {type(final_message).__name__}")
                    logger.info(f"Final message content preview: {str(final_message)[:200]}...")

                    response = final_message.content if hasattr(final_message, 'content') else str(final_message)
                    logger.info(f"Extracted response length: {len(response) if response else 0}")

                    if response:
                        logger.info(f"Response preview: {response[:200]}...")
                    else:
                        logger.warning("Response is empty!")
                        logger.warning(f"Final message details: {final_message}")

                    return response

                logger.warning(f"Unexpected agent result format: {result}")
                return str(result)
            else:
                # Fallback to direct LLM call
                logger.debug("Using direct LLM call (no tools)")
                system_prompt = persona_service.get_system_prompt()
                messages = [SystemMessage(content=system_prompt)]

                if chat_history:
                    messages.extend(chat_history)

                messages.append(HumanMessage(content=user_message))

                logger.debug(f"Calling LLM with {len(messages)} messages")
                response = await self.llm.ainvoke(messages)
                logger.debug(f"LLM response type: {type(response)}, has content: {hasattr(response, 'content')}")
                content = response.content if hasattr(response, 'content') else str(response)
                logger.debug(f"LLM response length: {len(content) if content else 0}")
                return content

        except Exception as e:
            logger.error(f"Agent call error: {e}", exc_info=True)
            raise

    async def generate_response(
        self,
        conversation_messages: List[Message],
        user_message: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> str:
        """
        Generate AI response with tool access and fallback.

        Args:
            conversation_messages: Previous messages in conversation
            user_message: Latest user message
            user_id: Slack user ID for tool calls (optional)
            user_name: User's display name for context (optional)

        Returns:
            AI-generated response or fallback
        """
        try:
            # Build conversation context
            chat_history = self._build_conversation_context(conversation_messages)

            # Build user context for tool calls
            user_context = None
            if user_id:
                user_context = {
                    "user_id": user_id,
                    "user_name": user_name or "Unknown"
                }

            # Call agent (we're already in an async context, just await)
            response = await self._call_agent(
                user_message,
                chat_history,
                use_tools=True,
                user_context=user_context
            )

            if not response or not response.strip():
                logger.warning("Agent returned empty response, using fallback")
                raise ValueError("Empty response from agent")

            logger.info(f"Generated response ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {e}")

            # Try without tools as fallback
            try:
                logger.info("Attempting fallback without tools...")
                chat_history = self._build_conversation_context(conversation_messages)

                # Build user context for fallback
                user_context = None
                if user_id:
                    user_context = {
                        "user_id": user_id,
                        "user_name": user_name or "Unknown"
                    }

                response = await self._call_agent(
                    user_message,
                    chat_history,
                    use_tools=False,
                    user_context=user_context
                )

                if not response or not response.strip():
                    raise ValueError("Empty response from fallback")

                logger.info("Fallback successful")
                return response
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}", exc_info=True)
                # Final fallback to persona service
                fallback = persona_service.get_fallback_response()
                logger.warning(f"Using emergency fallback response: '{fallback}'")
                return fallback

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses tiktoken for estimation (compatible with standard LLM service API).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # Rough fallback: ~4 chars per token
            return len(text) // 4

    async def cleanup(self):
        """Clean up MCP connections gracefully."""
        try:
            if self._mcp_tasks:
                logger.info(f"Cancelling {len(self._mcp_tasks)} MCP background task(s)...")

                for task in self._mcp_tasks:
                    if not task.done():
                        task.cancel()

                # Wait for all tasks to complete
                results = await asyncio.gather(*self._mcp_tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, asyncio.CancelledError):
                        logger.debug(f"MCP task {i} cancelled successfully")
                    elif isinstance(result, Exception):
                        logger.warning(f"Error during MCP task {i} cancellation: {result}")

            logger.info("MCP connections closed")
        except Exception as e:
            logger.error(f"Error during MCP cleanup: {e}")


# Global LLM agent service instance
# Note: initialize_mcp() must be called during app startup
llm_agent_service = LLMAgentService()
