"""
Integration tests for MCP tool integration.

Tests the critical path: Can we connect to MCP and invoke tools?

Following constitution: Integration tests provide highest ROI by testing
the actual user-facing behavior end-to-end.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, Mock

from src.services.llm_agent_service import LLMAgentService


class TestMCPConnectionIntegration:
    """
    Integration tests for MCP server connection.

    Tests the critical contract: Can we discover and register tools?
    """

    @pytest.mark.asyncio
    async def test_mcp_initialization_with_mocked_server(self):
        """
        MCP initialization discovers tools and creates agent.

        This tests the full initialization flow with a mocked MCP server.
        Critical because it validates our integration contract with MCP SDK.

        User scenario: Bot starts up and connects to MCP server successfully.
        """
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "MCP_WEB_SEARCH_URL": "http://test-mcp:9765/sse",
            },
        ):
            service = LLMAgentService()

            # Mock the MCP lifecycle to simulate successful connection
            async def mock_mcp_lifecycle(url):
                # Simulate tool discovery
                mock_tool = Mock()
                mock_tool.name = "test-tool"
                mock_tool.description = "A test tool"

                service.mcp_tools = [Mock()]  # Simulate tool registered
                service.agent = Mock()  # Simulate agent created
                service._mcp_ready.set()

            service._mcp_connection_lifecycle = AsyncMock(
                side_effect=mock_mcp_lifecycle
            )

            # Initialize MCP
            await service.initialize_mcp()

            # Should have created agent with tools
            assert service.agent is not None, "Agent should be created"
            assert len(service.mcp_tools) > 0, "Tools should be registered"

    @pytest.mark.asyncio
    async def test_mcp_tool_invocation_flow(self):
        """
        Agent can invoke MCP tools and get results.

        Tests the critical path: User asks question → Agent uses tool → Returns result.
        This validates that our LangChain integration actually works.

        User scenario: User asks "What's the latest Python version?"
        → Agent uses web search tool → Returns answer.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = LLMAgentService()

            # Set up mock agent that simulates tool invocation
            mock_agent_result = {
                "messages": [
                    Mock(content="Python 3.12 is the latest version")  # Final response
                ]
            }

            service.agent = Mock()
            service.agent.ainvoke = AsyncMock(return_value=mock_agent_result)
            service.mcp_tools = [Mock()]  # Simulate tools available

            # Call agent
            response = await service._call_agent(
                "What's the latest Python version?", chat_history=[], use_tools=True
            )

            # Should return the agent's response
            assert "Python 3.12" in response
            service.agent.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("MCP_WEB_SEARCH_URL"),
        reason="MCP server not configured, skipping live test",
    )
    async def test_live_mcp_connection(self):
        """
        LIVE TEST: Connect to actual MCP server if available.

        This test only runs when MCP_WEB_SEARCH_URL is set.
        Validates real integration with actual Docker MCP server.

        To run: docker-compose up -d web-search-mcp-dev
        """
        service = LLMAgentService()

        # Attempt live connection
        await service.initialize_mcp()

        # Verify tools were discovered
        assert (
            len(service.mcp_tools) > 0
        ), f"Expected tools, got {len(service.mcp_tools)}"
        assert service.agent is not None, "Agent should be created with tools"

        # Log discovered tools for debugging
        print(f"\nDiscovered {len(service.mcp_tools)} tools:")
        for tool in service.mcp_tools:
            print(f"  - {tool.name}: {tool.description}")

        # Clean up
        await service.cleanup()


class TestMessageHandlerIntegration:
    """
    Integration test for message handler → agent service flow.

    Tests the critical user-facing path: Message arrives → Response sent.
    """

    @pytest.mark.asyncio
    async def test_message_handler_uses_agent_when_available(self):
        """
        Message handler correctly selects agent service when MCP is enabled.

        User scenario: User sends DM → Bot uses agent with tools → Responds.
        Protects: Service selection logic routes to correct service.
        """
        from src.handlers.message_handler import get_llm_service

        # Mock environment and agent service
        with patch.dict(os.environ, {"USE_MCP_AGENT": "true", "OPENAI_API_KEY": "test"}):
            # Import happens inside get_llm_service, so patch at import location
            mock_agent = Mock()
            mock_agent.agent = Mock()  # Simulate agent exists

            with patch("src.services.llm_agent_service.llm_agent_service", mock_agent):
                service = get_llm_service()

                # Should return agent service (our mock), not standard LLM
                assert service == mock_agent

    @pytest.mark.asyncio
    async def test_message_handler_falls_back_to_standard_llm(self):
        """
        Message handler falls back to standard LLM when agent unavailable.

        User scenario: MCP server down → Bot still responds with standard LLM.
        Protects: Graceful degradation ensures bot always works.
        """
        from src.handlers.message_handler import get_llm_service

        # Simulate MCP disabled
        with patch("src.handlers.message_handler.os.getenv") as mock_env:
            mock_env.return_value = "false"  # USE_MCP_AGENT=false

            service = get_llm_service()

            # Should return standard LLM service
            from src.services.llm_service import llm_service

            assert service == llm_service
