# Implementation Plan: Lukas the Bear Slack Chatbot

**Branch**: `001-lukas-bear-chatbot` | **Date**: 2025-10-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-lukas-bear-chatbot/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Slack chatbot that embodies "Lukas the Bear", the office mascot, to enhance team engagement and communication. The bot will provide conversational AI responses maintaining a friendly bear persona, proactively message team members and participate in channel discussions, generate and post AI-created bear images, and execute utility commands for the team. Technical approach uses Python with Slack Bolt SDK for Slack integration, any-llm (Mozilla AI) for unified LLM provider access, and SQLite for persistent storage, all deployed as a Docker Compose stack.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Slack Bolt SDK (Socket Mode), any-llm (Mozilla AI unified LLM interface), OpenAI SDK (for DALL-E), APScheduler, SQLAlchemy, tenacity (retry), pybreaker (circuit breaker), mcp>=1.0.0 (official Model Context Protocol Python SDK), LangChain>=0.3.0, LangGraph>=0.2.0 (agent framework), starlette>=0.27.0 (ASGI framework for MCP SSE server), uvicorn>=0.24.0 (ASGI server)
**Storage**: SQLite database for conversation history, configuration, and scheduled tasks
**Testing**: pytest for unit tests, pytest-asyncio for async tests, integration tests for Slack/LLM APIs and MCP servers
**Target Platform**: Linux Docker containers (Docker Compose stack)
**Project Type**: Single Python application with background task scheduling and co-located MCP server
**Deployment**: Docker Compose with bot service (multi-process container), external MCP server containers, and persisted SQLite volume
**MCP Integration**: Multi-server architecture with two MCP servers:
  1. **web-search-mcp** (Node.js/TypeScript) - External container providing web search tools (full-web-search, get-web-search-summaries, get-single-web-page-content)
  2. **slack-operations-mcp** (Python/Starlette) - Co-located in bot container providing Slack command tools (post_message_to_channel, create_reminder, get_team_info, update_bot_config, generate_and_post_image)

  Connected via official MCP Python SDK using SSE transport. Background task lifecycle maintains persistent SSE connections throughout bot lifetime. Service selection via USE_MCP_AGENT env var with three-tier fallback (agent with tools → LLM without tools → emergency response). LangGraph create_react_agent enables autonomous tool selection from 8 total tools across both servers.
**Performance Goals**: <5s response time for DMs, handle 10 concurrent conversations, 99% uptime during business hours
**Constraints**: Slack API rate limits (1+ msg/sec per channel), LLM provider limits (handled via any-llm), SQLite suitable for <50 users
**Scale/Scope**: Single Slack workspace, <50 team members, ~100-500 messages/day estimated load
**Image Generation**: DALL-E 3 via OpenAI API (1024x1024, ~1 image/week usage)
**Task Scheduling**: APScheduler with SQLAlchemy job store (sufficient for single-instance deployment)
**LLM Context Management**: Sliding window of last 10 message pairs (~4k tokens max), token-based truncation using tiktoken
**Error Recovery**: Exponential backoff (3 retries, 1s-4s delays) + circuit breaker (5 failure threshold) + graceful degradation with fallback responses

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md`:

### Principle 1: Documentation & Code Clarity
- [x] Documentation plan includes API docs for public interfaces (Slack event handlers, LLM client, scheduler interface)
- [x] Complex algorithms/logic identified for explanatory comments (persona system prompt generation, engagement probability calculation, conversation context management)
- [x] Comments will explain "why" and context, not just "what" (e.g., "Use APScheduler not Celery because we don't need distributed tasks for single-workspace deployment")

### Principle 2: Smart Architecture & Design
- [x] Architecture choices justified by concrete current needs (Slack Bolt for event handling, any-llm for LLM provider flexibility, SQLite for simple single-instance deployment)
- [x] Simpler alternatives considered and documented if rejected (research.md will document: Bolt vs raw Slack API, APScheduler vs Celery, SQLite vs PostgreSQL)
- [x] No premature abstractions (wait for 2-3 use cases before abstracting) - Direct implementations first, extract patterns only when repeated
- [x] YAGNI applied: complexity deferred until proven necessary (No Redis caching, no microservices, no Kubernetes - Docker Compose sufficient for scope)

### Principle 3: Pragmatic Testing (80/20 Rule)
- [x] Test strategy focuses on critical user journeys (contract/integration) - Integration tests for Slack event handling, LLM response generation, scheduled task execution
- [x] High-impact business logic identified for testing (persona prompt generation, command parsing, engagement probability logic, conversation context retrieval)
- [x] NOT targeting 100% coverage - only high-value tests planned (Skip testing Slack SDK internals, focus on our business logic and integration points)
- [x] Tests planned are maintainable and fast (Mock Slack/LLM APIs for unit tests, use pytest fixtures for common setups, integration tests with test workspace)

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
lukas_chat_bear/
├── src/
│   ├── __init__.py
│   ├── bot.py                    # Main Slack Bolt app initialization
│   ├── mcp_server.py             # MCP server exposing Slack operations as tools (port 9766)
│   ├── handlers/                 # Slack event handlers
│   │   ├── __init__.py
│   │   ├── message_handler.py    # DM and mention handling
│   │   ├── thread_handler.py     # Channel thread monitoring
│   │   └── command_handler.py    # Simplified - routes mentions to LLM agent
│   ├── services/                 # Core business logic
│   │   ├── __init__.py
│   │   ├── llm_service.py        # any-llm integration (standard mode)
│   │   ├── llm_agent_service.py  # MCP-enabled agent with multi-server tool access
│   │   ├── command_service.py    # Framework-agnostic command execution logic (shared by Slack + MCP)
│   │   ├── image_service.py      # AI image generation
│   │   ├── persona_service.py    # Lukas bear persona management
│   │   ├── engagement_service.py # Probability-based engagement logic
│   │   └── scheduler_service.py  # Background task scheduling
│   ├── models/                   # SQLAlchemy data models
│   │   ├── __init__.py
│   │   ├── conversation.py       # ConversationSession entity
│   │   ├── team_member.py        # TeamMember entity
│   │   ├── scheduled_task.py     # ScheduledTask entity
│   │   └── config.py             # Configuration entity
│   ├── repositories/             # Data access layer
│   │   ├── __init__.py
│   │   ├── conversation_repo.py
│   │   ├── team_member_repo.py
│   │   └── config_repo.py
│   └── utils/                    # Shared utilities
│       ├── __init__.py
│       ├── logger.py             # Logging configuration
│       └── retry.py              # Retry/backoff utilities
│
├── tests/
│   ├── integration/              # Slack + LLM + MCP integration tests
│   │   ├── test_slack_events.py
│   │   ├── test_llm_integration.py
│   │   ├── test_mcp_integration.py    # MCP server connection and tool invocation tests
│   │   └── test_scheduled_tasks.py
│   ├── unit/                     # Business logic unit tests
│   │   ├── test_persona_service.py
│   │   ├── test_engagement_logic.py
│   │   └── services/
│   │       └── test_command_service.py # Framework-agnostic command logic tests
│   └── fixtures/                 # Test data and mocks
│       └── slack_events.json
│
├── docker/
│   ├── Dockerfile                # Bot container build configuration (multi-process)
│   ├── start-bot.sh              # Startup script: MCP server (background) + Slack bot (foreground)
│   └── mcp-servers/              # External MCP server containers
│       └── web-search/           # Web search MCP server
│           └── Dockerfile        # Node.js container with Supergateway bridge
│
├── config/
│   ├── config.example.yml        # Example configuration
│   └── persona_prompts.yml       # Lukas persona system prompts
│
├── migrations/                   # SQLAlchemy Alembic migrations
│   └── versions/
│
├── data/                         # SQLite database (created at runtime)
│
├── docker-compose.yml            # Docker Compose orchestration (root level)
├── pyproject.toml                # Python project config (PEP 621, managed by uv)
├── uv.lock                       # Locked dependencies (generated by uv)
├── CHANGELOG.md                  # Version history and changes
├── README.md
└── .env.example                  # Example environment variables
```

**Structure Decision**: Single Python application (Option 1) with clean separation of concerns. Slack Bolt handlers in `handlers/` delegate to business logic in `services/`, which use `repositories/` for data access. This structure keeps Slack-specific code isolated from core logic, making it easier to test and potentially adapt to other platforms later. SQLAlchemy models in `models/` define the database schema.

**Modern Python Tooling**: Uses `pyproject.toml` (PEP 621 standard) with `uv` package manager for fast, reliable dependency management. Docker Compose file at root level for convenient `docker compose up` commands.

**MCP Architecture**: Multi-server architecture with three MCP components:

1. **Web Search MCP** (external container, Node.js): Provides web search tools (full-web-search, get-web-search-summaries, get-single-web-page-content) via SSE transport on port 9765. Supergateway bridges stdio-based MCP tools to network-accessible SSE.

2. **Slack Operations MCP** (co-located in bot container, Python/Starlette): Exposes 5 Slack command tools on port 9766:
   - `post_message_to_channel` - Post messages to Slack channels with attribution
   - `create_reminder` - Schedule reminders with flexible time parsing
   - `get_team_info` - Query team members, bot status, engagement stats
   - `update_bot_config` - Update bot configuration (admin-only)
   - `generate_and_post_image` - Generate AI images and post to channels (admin-only)

3. **Command Service Layer**: Framework-agnostic business logic (`CommandService` class) shared between direct Slack handlers and MCP tools. Returns structured dicts instead of formatted strings, enabling protocol-independent command execution. Zero code duplication between Slack and MCP paths.

The official MCP Python SDK manages persistent SSE connections with background task lifecycle pattern. LangGraph's `create_react_agent` framework converts all 8 MCP tools (3 web search + 5 Slack operations) to LangChain `StructuredTool` instances, enabling autonomous tool selection based on natural language queries. Multi-process container startup: MCP server launches in background (port 9766), then Slack bot in foreground.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. All complexity is justified by current needs:
- Repository pattern needed for clean testability (mock data layer in tests)
- Service layer needed to separate Slack SDK from business logic
- APScheduler needed for time-based proactive engagement (core requirement)
- Docker Compose needed for deployment isolation and reproducibility
- MCP architecture enables natural language command processing via LLM agent (core UX requirement)
- CommandService extraction eliminates code duplication between Slack and MCP protocols

---

## MCP Command System Implementation

**Completed**: 2025-10-27

### Architecture Decision: Natural Language Commands via MCP

**Problem**: Original regex-based command parsing required exact syntax, poor UX for users who had to memorize specific command formats.

**Solution**: Replace regex parsing with MCP tool-based architecture where LLM agent understands natural language intent and autonomously selects appropriate tools.

### Implementation Components

**1. CommandService (src/services/command_service.py)** - 620 lines
- Framework-agnostic business logic extracted from CommandExecutor
- Shared by both Slack handlers and MCP server (zero duplication)
- Returns structured dicts instead of formatted strings for protocol flexibility
- Methods: `post_message()`, `create_reminder()`, `get_info()`, `update_config()`, `generate_image()`

**2. Slack Operations MCP Server (src/mcp_server.py)** - 280 lines
- Starlette/Uvicorn ASGI server exposing 5 Slack operations as MCP tools
- Port 9766, SSE transport for persistent connections
- Tool schema definitions enable LLM to understand when to invoke each tool
- Delegates all business logic to CommandService for code reuse

**3. Multi-Process Startup (docker/start-bot.sh)** - 40 lines
- Launches MCP server in background (process 1)
- Launches Slack bot in foreground (process 2)
- Health checks and cleanup on shutdown
- Single container deployment (no additional orchestration needed)

**4. Multi-Server LLM Agent (src/services/llm_agent_service.py)** - Updated
- Connects to both web-search and slack-operations MCP servers
- Manages multiple SSE sessions and background tasks
- Collects all tools (8 total) for unified agent decision-making
- LangGraph `create_react_agent` enables autonomous tool selection

**5. Simplified Command Handler (src/handlers/command_handler.py)** - Reduced from 1340 to 180 lines (87% reduction)
- Removed: CommandParser class (230 lines of regex patterns)
- Removed: CommandExecutor implementation (600+ lines)
- All @mentions now route to LLM agent which decides tool usage
- Kept: Helper functions and ConfirmationFormatter for backwards compatibility

### Benefits Over Regex Parsing

| Aspect | Before (Regex) | After (MCP) |
|--------|---------------|-------------|
| **User Experience** | Exact syntax required | Natural language variations work |
| **Flexibility** | Adding commands = regex engineering | Adding commands = tool descriptions |
| **Code Duplication** | Command logic in one file | Shared CommandService layer |
| **Testing** | Coupled to Slack protocol | Framework-agnostic unit tests |
| **Maintainability** | 1340 lines command handler | 180 lines + 620 lines reusable service |

### Test Coverage

**Unit Tests** (tests/unit/services/test_command_service.py) - 16 tests
- All command types tested independently
- Permission enforcement (admin vs public)
- Edge cases (invalid formats, missing users)
- Helper methods (time parsing, duration parsing)

**Integration Tests** (tests/integration/test_mcp_integration.py) - 7 tests
- MCP server connection and tool discovery
- Multi-server agent initialization
- Tool invocation flow end-to-end
- Live MCP server tests (conditional on env var)

**Test Results**: 21/23 tests pass (2 skipped as expected for live server tests)

### Performance Characteristics

- **Latency**: ~800-1200ms (vs ~50ms regex) - acceptable for conversational UX
- **Cost**: ~$0.001-0.002 per command (LLM inference)
- **Reliability**: Three-tier fallback ensures bot always responds
- **Resource Usage**: +1 background process (MCP server), ~50MB additional memory

### Natural Language Examples Supported

**Reminders**:
- "remind me in 30 minutes to check the build"
- "ping me in half an hour about the build"
- "can you remind me tomorrow at 3pm to review PRs"

**Posting**:
- "post 'Meeting at 3pm' to #general"
- "send a message to the team channel saying we're done"
- "announce in #dev that the build is complete"

**Info Queries**:
- "team info" / "who's on the team"
- "what's the bot status"
- "show me engagement stats"

**Admin Commands**:
- "set dm interval to 48 hours"
- "update thread probability to 0.4"
- "generate a halloween image to #random"

---

## Phase 0: Research Summary

**Completed**: 2025-10-24
**Output**: `research.md`

### Decisions Made:

1. **Image Generation**: DALL-E 3 (OpenAI) - chose quality and simplicity over cost
2. **Task Scheduling**: APScheduler - simple in-process scheduling sufficient for single-instance
3. **LLM Context Management**: Sliding window (10 message pairs) with token-based truncation
4. **Error Recovery**: Exponential backoff + circuit breaker + graceful degradation

### Key Trade-offs:

| Decision | Chose | Over | Reason |
|----------|-------|------|--------|
| Image API | DALL-E 3 | Stable Diffusion, Midjourney | API simplicity, quality, safety |
| Scheduler | APScheduler | Celery | No broker needed for current scale |
| Slack Integration | Socket Mode | Events API | Simpler setup, no public endpoint |
| Database | SQLite | PostgreSQL | Deployment simplicity for <50 users |

All decisions align with Constitution Principle 2 (Smart Architecture): chose simplicity appropriate to current needs.

---

## Phase 1: Design Artifacts

**Completed**: 2025-10-24

### Data Model (`data-model.md`)

**7 Core Entities**:
1. ConversationSession - Ongoing dialogues with context
2. Message - Individual messages with token tracking
3. TeamMember - User profiles and admin status
4. ScheduledTask - Proactive DMs, image posts, cleanup jobs
5. Configuration - Runtime settings persistence
6. EngagementEvent - Audit log for thread engagement decisions
7. GeneratedImage - AI image generation tracking

**Estimated DB Size**: ~13 MB after 6 months (well within SQLite capabilities)

### API Contracts (`contracts/`)

**Two Contract Documents**:

1. **slack-events.md**: Slack Bolt event handlers
   - Message events (DMs, mentions, channel monitoring)
   - Bot-initiated actions (proactive DMs, image posts)
   - Error handling patterns
   - OAuth scope requirements

2. **llm-api.md**: External AI service integration
   - any-llm (Mozilla AI) chat completion with multi-provider support
   - OpenAI DALL-E 3 (image generation)
   - Retry policies and circuit breakers
   - Cost tracking and fallback strategies

### Quickstart Guide (`quickstart.md`)

**11 Comprehensive Sections**:
- Slack app setup (OAuth scopes, Socket Mode)
- LLM provider configuration (any-llm setup)
- OpenAI API setup
- Local development environment
- Docker Compose deployment
- Testing procedures
- Production deployment
- Troubleshooting guide
- Customization options
- Maintenance procedures
- Configuration reference

**Estimated Setup Time**: 30-45 minutes for first-time setup

### Agent Context Update

**Updated**: `CLAUDE.md`
- Added Python 3.11+ as language
- Added Slack Bolt, any-llm, OpenAI SDK, APScheduler, SQLAlchemy dependencies
- Added SQLite database context
- Preserves any manual additions between markers

---

## Constitution Re-Validation (Post-Design)

### Principle 1: Documentation & Code Clarity ✅

**Compliance**:
- ✅ Quickstart guide provides comprehensive setup documentation
- ✅ API contracts document all external integrations (Slack, LLM, DALL-E)
- ✅ Data model fully documented with business rules and relationships
- ✅ Research decisions documented with rationale
- ✅ Code structure (seen in project tree) separates concerns clearly

**Planned Documentation** (during implementation):
- Docstrings for all public functions explaining purpose, args, returns
- Comments explaining "why" for complex logic (persona prompt generation, engagement probability)
- Examples in contracts show usage patterns

### Principle 2: Smart Architecture & Design ✅

**Compliance**:
- ✅ All architectural choices justified by current needs (see research.md)
- ✅ Simpler alternatives documented and rejected with clear reasoning
- ✅ No premature abstractions: Repository pattern only added for testability (concrete need)
- ✅ YAGNI applied: No Redis, no Kubernetes, no microservices, no message broker
- ✅ Complexity deferred: Image URL caching (Phase 2), conversation summarization (Phase 2)

**Justified Complexity**:
- Slack Bolt SDK: Abstracts event handling complexity (appropriate)
- Service layer: Enables testing Slack handlers without SDK dependencies
- Repository pattern: Allows mocking database in tests
- Circuit breaker: Prevents cascading failures from external API outages

All complexity maps to concrete requirements from spec.md.

### Principle 3: Pragmatic Testing (80/20 Rule) ✅

**Compliance**:
- ✅ Test strategy focuses on critical paths:
  - Integration: Slack event handling, LLM responses, scheduled tasks
  - Unit: Engagement probability logic, command parsing, persona prompts
- ✅ High-impact business logic identified: conversation context, engagement decisions
- ✅ NOT targeting 100% coverage:
  - Skip testing Slack SDK internals (third-party code)
  - Skip testing database ORM (SQLAlchemy tested by maintainers)
  - Focus on our business logic and integration points
- ✅ Tests designed for maintainability:
  - Mock external APIs (Slack, LLM, DALL-E) in unit tests
  - Test workspace for integration tests
  - Pytest fixtures for common setups

**High-Value Test Scenarios** (from contracts):
- DM message → persona-appropriate response (integration)
- Thread engagement probability calculation (unit)
- Proactive DM scheduling and execution (integration)
- Image generation and posting (integration)
- Command parsing edge cases (unit)
- Error recovery and fallback responses (unit + integration)

**Estimated Coverage**: ~70-80% line coverage, 100% critical path coverage

---

## Final Design Validation

**Gate Check**: ✅ ALL PASS

- [x] Constitution compliance verified
- [x] All NEEDS CLARIFICATION items resolved
- [x] Technical context complete and concrete
- [x] Data model documented with entities, relationships, indexes
- [x] API contracts defined with request/response formats
- [x] Error handling patterns established
- [x] Setup documentation written (quickstart.md)
- [x] Agent context updated

**Readiness**: ✅ Ready to proceed to `/speckit.tasks`

---

## Next Phase: Task Generation

**Command**: `/speckit.tasks`

**Will Generate**: `tasks.md`

**Expected Task Breakdown**:
- Phase 1: Setup (project initialization, Docker, dependencies)
- Phase 2: Foundation (database models, migrations, config loading)
- Phase 3-6: User Stories (P1: Direct conversation, P2: Proactive engagement, P3: Image posting, P4: Commands)
- Phase N: Polish (documentation, testing, deployment)

**Task Count Estimate**: 40-60 tasks across all user stories

---

## Summary

**Branch**: `001-lukas-bear-chatbot`
**Status**: Planning Complete ✅
**Artifacts**:
- ✅ plan.md (this file)
- ✅ research.md (technology decisions)
- ✅ data-model.md (database schema)
- ✅ contracts/slack-events.md (Slack integration)
- ✅ contracts/llm-api.md (AI services)
- ✅ quickstart.md (setup guide)
- ✅ CLAUDE.md (agent context updated)

**Ready for**: Task generation and implementation

**Estimated Implementation Time**: 3-4 weeks (1 developer, part-time)

**First Milestone**: P1 user story (Direct conversation) = MVP (~1 week)
