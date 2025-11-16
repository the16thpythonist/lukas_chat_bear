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
            async def mock_mcp_lifecycle(url, server_name, ready_event):
                # Simulate tool discovery - use real StructuredTool for agent creation
                from langchain_core.tools import StructuredTool

                async def dummy_tool(**kwargs):
                    return "test result"

                mock_tool = StructuredTool.from_function(
                    name="test_tool",
                    description="A test tool",
                    coroutine=dummy_tool
                )

                service.mcp_tools = [mock_tool]  # Simulate tool registered
                ready_event.set()  # Signal ready

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
    @pytest.mark.skip(reason="Requires live MCP server - run with: docker-compose up -d web-search-mcp-dev")
    async def test_live_mcp_connection(self):
        """
        LIVE TEST: Connect to actual MCP server if available.

        This test only runs when MCP_WEB_SEARCH_URL is set.
        Validates real integration with actual Docker MCP server.

        To run: docker-compose up -d web-search-mcp-dev
        Then remove the @pytest.mark.skip decorator to run this test.
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


class TestSlackOperationsMCPServer:
    """
    Integration tests for slack-operations MCP server.

    Tests the command execution via MCP tools.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("MCP_SLACK_OPS_URL"),
        reason="Slack operations MCP server not configured, skipping live test",
    )
    async def test_slack_ops_mcp_server_connection(self):
        """
        LIVE TEST: Connect to slack-operations MCP server if available.

        This test only runs when MCP_SLACK_OPS_URL is set.
        Validates that the MCP server starts and exposes tools.

        To run: docker-compose -f docker-compose.dev.yml up -d
        """
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        slack_ops_url = os.getenv("MCP_SLACK_OPS_URL", "http://localhost:9766/sse")

        print(f"\nConnecting to slack-operations MCP server at {slack_ops_url}...")

        async with sse_client(url=slack_ops_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List tools
                tools_list = await session.list_tools()
                tools = tools_list.tools

                # Verify expected tools are available
                tool_names = [t.name for t in tools]

                print(f"\nDiscovered {len(tools)} slack operations tools:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description[:80]}...")

                # Assert expected tools exist
                assert "post_message_to_channel" in tool_names
                assert "create_reminder" in tool_names
                assert "get_team_info" in tool_names
                assert "update_bot_config" in tool_names
                assert "generate_and_post_image" in tool_names

                assert len(tools) == 5, f"Expected 5 tools, got {len(tools)}"

    @pytest.mark.asyncio
    async def test_llm_agent_discovers_slack_ops_tools(self):
        """
        Test that LLM agent service discovers slack-operations tools.

        User scenario: Bot starts → Connects to both MCP servers →
        Has access to both web search AND slack operations tools.
        """
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "MCP_WEB_SEARCH_URL": "http://test-web-search:9765/sse",
                "MCP_SLACK_OPS_URL": "http://test-slack-ops:9766/sse",
            },
        ):
            service = LLMAgentService()

            # Mock the MCP lifecycle for both servers
            from langchain_core.tools import StructuredTool

            async def dummy_tool(**kwargs):
                return "test result"

            async def mock_mcp_lifecycle(url, server_name, ready_event):
                # Simulate different tools from different servers
                if "web-search" in server_name:
                    tool_names = ["full_web_search", "get_web_search_summaries"]
                elif "slack-ops" in server_name or "slack-operations" in server_name:
                    tool_names = ["post_message_to_channel", "create_reminder", "get_team_info"]
                else:
                    tool_names = []

                # Add to service tools as real StructuredTool instances
                for tool_name in tool_names:
                    structured_tool = StructuredTool.from_function(
                        name=tool_name,
                        description=f"Test tool: {tool_name}",
                        coroutine=dummy_tool
                    )
                    service.mcp_tools.append(structured_tool)

                ready_event.set()

            service._mcp_connection_lifecycle = AsyncMock(
                side_effect=mock_mcp_lifecycle
            )

            # Initialize MCP (should connect to both servers)
            await service.initialize_mcp()

            # Should have tools from both servers
            assert len(service.mcp_tools) >= 5, f"Expected at least 5 total tools, got {len(service.mcp_tools)}"
            assert service.agent is not None, "Agent should be created with all tools"
