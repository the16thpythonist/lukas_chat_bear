# lukas_chat_bear Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-27

## Active Technologies

- Python 3.11+ + Slack Bolt SDK (Socket Mode), any-llm (Mozilla AI unified LLM interface), OpenAI SDK (for DALL-E), APScheduler, SQLAlchemy, tenacity (retry), pybreaker (circuit breaker), MCP SDK >=1.0.0 (Model Context Protocol), LangChain >=0.3.0, LangGraph >=0.2.0 (agent framework), Starlette >=0.27.0 (ASGI framework), Uvicorn >=0.24.0 (ASGI server) (001-lukas-bear-chatbot)

## Project Structure

```text
src/
├── bot.py                    # Main Slack Bolt app
├── mcp_server.py             # MCP server exposing Slack operations (port 9766)
├── handlers/                 # Slack event handlers
├── services/
│   ├── llm_service.py        # Standard LLM service
│   ├── llm_agent_service.py  # MCP-enabled agent (multi-server support)
│   ├── command_service.py    # Framework-agnostic command logic
│   └── ...
├── models/                   # SQLAlchemy models
└── repositories/             # Data access layer

tests/
├── unit/
│   └── services/
│       └── test_command_service.py
└── integration/
    └── test_mcp_integration.py

docker/
├── Dockerfile
├── start-bot.sh              # Multi-process startup (MCP + Bot)
└── mcp-servers/              # External MCP server containers
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes

- 2025-10-27: MCP Command System Migration - Replaced regex-based command parsing with MCP tool-based natural language processing. Created CommandService (framework-agnostic), slack-operations MCP server (5 tools), multi-server agent architecture. 87% code reduction in command_handler.py.
- 2025-10-26: MCP Integration - Added web-search capabilities via Model Context Protocol with LangGraph agent framework

<!-- MANUAL ADDITIONS START -->

## Environment Setup

Before running any commands, activate the virtual environment:

```bash
source .venv/bin/activate
```

## Issue Resolution

When encountering issues or errors:

1. First, attempt to resolve the issue yourself by analyzing error messages, checking logs, and reviewing relevant code
2. If the issue persists or is unclear, use Web Search to look online for possible solutions, error explanations, and best practices
3. Search for specific error messages, stack traces, or problem descriptions to find relevant discussions and solutions

## Docker Development

**IMPORTANT:** For debugging and development, ALWAYS use the dev containers only:

```bash
# Start dev containers
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker logs lukas-bear-bot-dev -f

# Stop dev containers
docker-compose -f docker-compose.dev.yml down
```

**Do NOT use both docker-compose.yml and docker-compose.dev.yml together** unless explicitly deploying production.

## MCP Architecture

The bot uses a **multi-server MCP architecture** for enhanced capabilities:

### MCP Servers

1. **Web Search MCP** (external container, Node.js, port 9765)
   - Provides web search tools for current information queries
   - Tools: `full-web-search`, `get-web-search-summaries`, `get-single-web-page-content`

2. **Slack Operations MCP** (co-located in bot container, Python/Starlette, port 9766)
   - Exposes Slack command operations as MCP tools
   - Tools: `post_message_to_channel`, `create_reminder`, `get_team_info`, `update_bot_config`, `generate_and_post_image`
   - Shares database and Slack client with main bot

### Command System Architecture

**Natural Language Processing**: Commands are processed via LLM agent with MCP tools instead of regex patterns

**Benefits**:
- Users can phrase commands naturally (multiple variations work)
- No need to memorize exact command syntax
- LLM agent autonomously selects appropriate tools based on intent

**Code Reuse**: CommandService class (`src/services/command_service.py`) provides framework-agnostic business logic shared between:
- Slack handlers (for backwards compatibility)
- MCP server tools (for agent tool invocation)

**Multi-Process Container**: Single Docker container runs two processes:
1. MCP server (background, port 9766) - started by `docker/start-bot.sh`
2. Slack bot (foreground, Socket Mode) - main application

### Service Selection

The bot uses intelligent service selection based on configuration:

- `USE_MCP_AGENT=true` → LLM agent with MCP tools (8 tools from 2 servers)
- `USE_MCP_AGENT=false` → Standard LLM service (no tools)
- Fallback hierarchy: agent with tools → LLM without tools → emergency response

### Example Natural Language Commands

**Instead of exact syntax**, users can now say:
- "remind me in 30 minutes to check the build" OR "ping me in half an hour about the build"
- "post 'Meeting at 3pm' to #general" OR "send a message to the team saying meeting at 3pm"
- "team info" OR "who's on the team" OR "show me the team roster"

<!-- MANUAL ADDITIONS END -->
