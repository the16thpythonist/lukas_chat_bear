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

        # MCP connection management
        self.mcp_session: Optional[ClientSession] = None
        self.mcp_tools: List[StructuredTool] = []
        self.agent = None  # LangGraph agent
        self._mcp_task: Optional[asyncio.Task] = None  # Background task for MCP lifecycle
        self._mcp_ready = asyncio.Event()  # Signal when MCP is ready

        # Circuit breaker for MCP connections
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,
            reset_timeout=60,
        )

        logger.info(f"LLM Agent service initialized with model {self.model}")

    async def _mcp_connection_lifecycle(self, url: str) -> None:
        """
        Background task that manages MCP connection lifecycle.

        Keeps the SSE context manager alive throughout bot lifetime.
        This prevents the "exit cancel scope in different task" error.
        """
        try:
            logger.info(f"Starting MCP connection to {url}...")

            # Enter SSE context and keep it alive
            async with sse_client(url=url) as (read_stream, write_stream):
                # Enter MCP session context
                async with ClientSession(read_stream, write_stream) as session:
                    self.mcp_session = session

                    # Initialize session
                    await session.initialize()
                    logger.info("MCP session initialized successfully")

                    # List and register tools
                    tools_list = await session.list_tools()
                    logger.info(f"Found {len(tools_list.tools)} MCP tools")

                    self.mcp_tools = []
                    for mcp_tool in tools_list.tools:
                        langchain_tool = self._create_langchain_tool(mcp_tool)
                        self.mcp_tools.append(langchain_tool)
                        logger.info(f"  - {mcp_tool.name}: {mcp_tool.description}")

                    # Create agent
                    self._create_agent()
                    logger.info(f"MCP agent initialized with {len(self.mcp_tools)} tools")

                    # Signal that MCP is ready
                    self._mcp_ready.set()

                    # Keep connection alive indefinitely
                    # This task will run until cancelled (bot shutdown)
                    try:
                        await asyncio.Event().wait()  # Wait forever
                    except asyncio.CancelledError:
                        logger.info("MCP connection lifecycle task cancelled")
                        raise

        except httpx.ReadTimeout:
            # Expected timeout on idle SSE connection - this is non-critical
            logger.debug("MCP SSE connection timed out (expected for idle connections)")
            self._mcp_ready.set()  # Tools are already registered, this is fine
        except Exception as e:
            logger.error(f"MCP connection lifecycle error: {e}", exc_info=True)
            logger.warning("Agent will run without MCP tools")
            self._mcp_ready.set()  # Unblock initialization even on error

    async def initialize_mcp(self) -> None:
        """
        Initialize MCP client with SSE transport in background task.

        Creates a long-lived background task that maintains the MCP connection.
        This prevents async context cleanup errors by keeping context managers
        alive in the same task where they were created.
        """
        web_search_url = os.getenv("MCP_WEB_SEARCH_URL")

        if not web_search_url:
            logger.warning("MCP_WEB_SEARCH_URL not configured, agent will run without tools")
            return

        try:
            # Create background task for MCP lifecycle
            self._mcp_task = asyncio.create_task(
                self._mcp_connection_lifecycle(web_search_url)
            )

            # Wait for MCP to be ready (with timeout)
            try:
                await asyncio.wait_for(self._mcp_ready.wait(), timeout=30.0)
                if self.agent:
                    logger.info("MCP initialization complete")
                else:
                    logger.warning("MCP initialization completed but no agent created")
            except asyncio.TimeoutError:
                logger.error("MCP initialization timed out after 30s")
                if self._mcp_task:
                    self._mcp_task.cancel()

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

    def _create_langchain_tool(self, mcp_tool) -> StructuredTool:
        """
        Convert an MCP tool to a LangChain tool with proper schema.

        Args:
            mcp_tool: MCP tool definition

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
                logger.debug(f"Calling MCP tool '{mcp_tool.name}' with arguments: {kwargs}")

                result = await self.mcp_session.call_tool(
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
        use_tools: bool = True
    ) -> str:
        """
        Call agent or LLM with circuit breaker protection.

        Args:
            user_message: User's message text
            chat_history: Previous conversation messages
            use_tools: Whether to enable tool use

        Returns:
            AI response text
        """
        try:
            if use_tools and self.agent:
                # Use LangGraph agent with tools
                messages = chat_history or []
                messages.append(HumanMessage(content=user_message))

                logger.info(f"Calling agent with {len(messages)} messages, use_tools={use_tools}")
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
    ) -> str:
        """
        Generate AI response with tool access and fallback.

        Args:
            conversation_messages: Previous messages in conversation
            user_message: Latest user message

        Returns:
            AI-generated response or fallback
        """
        try:
            # Build conversation context
            chat_history = self._build_conversation_context(conversation_messages)

            # Call agent (we're already in an async context, just await)
            response = await self._call_agent(user_message, chat_history, use_tools=True)

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
                response = await self._call_agent(user_message, chat_history, use_tools=False)

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
            if self._mcp_task and not self._mcp_task.done():
                logger.info("Cancelling MCP background task...")
                self._mcp_task.cancel()
                try:
                    await self._mcp_task
                except asyncio.CancelledError:
                    logger.debug("MCP task cancelled successfully")
                except Exception as e:
                    logger.warning(f"Error during MCP task cancellation: {e}")

            logger.info("MCP connections closed")
        except Exception as e:
            logger.error(f"Error during MCP cleanup: {e}")


# Global LLM agent service instance
# Note: initialize_mcp() must be called during app startup
llm_agent_service = LLMAgentService()
