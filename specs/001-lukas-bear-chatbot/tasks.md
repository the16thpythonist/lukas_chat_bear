# Tasks: Lukas the Bear Slack Chatbot

**Input**: Design documents from `/specs/001-lukas-bear-chatbot/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in the specification. Test tasks are included following the 80/20 rule (Pragmatic Testing) from the constitution - focusing on critical user journeys and high-impact business logic only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure (src/, tests/, config/, docker/, migrations/, data/)
- [X] T002 Initialize pyproject.toml with project metadata and dependencies (Slack Bolt, any-llm, OpenAI SDK, APScheduler, SQLAlchemy, tenacity, pybreaker, pytest)
- [X] T003 [P] Create .env.example with required environment variables (SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_PROVIDER, OPENAI_API_KEY, etc.)
- [X] T004 [P] Create .gitignore for Python project (.env, __pycache__, .venv, data/*.db)
- [X] T005 [P] Setup logging configuration in src/utils/logger.py
- [X] T006 [P] Create config/config.example.yml with bot configuration structure
- [X] T007 [P] Create config/persona_prompts.yml with Lukas the Bear system prompt and fallback responses
- [X] T008 [P] Create docker/Dockerfile for Python application
- [X] T009 Create docker-compose.yml at project root with bot service and volume mounts
- [X] T010 [P] Create README.md with project overview and setup instructions
- [X] T011 [P] Initialize CHANGELOG.md following Keep a Changelog format

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T012 Setup Alembic for database migrations in migrations/ directory
- [X] T013 [P] Create SQLAlchemy base model in src/models/__init__.py
- [X] T014 [P] Create database connection and session management in src/utils/database.py
- [X] T015 [P] Create ConversationSession model in src/models/conversation.py
- [X] T016 [P] Create Message model in src/models/message.py
- [X] T017 [P] Create TeamMember model in src/models/team_member.py
- [X] T018 [P] Create ScheduledTask model in src/models/scheduled_task.py
- [X] T019 [P] Create Configuration model in src/models/config.py
- [X] T020 [P] Create EngagementEvent model in src/models/engagement_event.py
- [X] T021 [P] Create GeneratedImage model in src/models/generated_image.py
- [X] T022 Generate initial Alembic migration for all models
- [X] T023 [P] Create conversation repository in src/repositories/conversation_repo.py
- [X] T024 [P] Create team member repository in src/repositories/team_member_repo.py
- [X] T025 [P] Create configuration repository in src/repositories/config_repo.py
- [X] T026 [P] Create retry utilities with tenacity in src/utils/retry.py
- [X] T027 Create configuration loader in src/utils/config_loader.py (loads YAML + env vars)
- [X] T028 Create main Slack Bolt app initialization in src/bot.py
- [X] T029 Setup APScheduler with SQLAlchemy job store in src/services/scheduler_service.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Direct Conversation with Lukas (Priority: P1) 🎯 MVP

**Goal**: Team members can initiate direct message conversations with Lukas the Bear and receive personality-driven responses

**Independent Test**: Team member can send a direct message to Lukas asking "What's the weather like today?" and receive a personality-driven response within 5 seconds. Can also ask about team information and get relevant answers while maintaining conversation context.

### Tests for User Story 1

> **NOTE: Tests focus on critical paths only (80/20 rule)**

- [X] T030 [P] [US1] Create unit test for persona prompt generation in tests/unit/test_persona_service.py
- [X] T031 [P] [US1] Create unit test for conversation context building in tests/unit/test_llm_service.py
- [X] T032 [P] [US1] Create integration test for DM message handling in tests/integration/test_slack_events.py
- [X] T033 [P] [US1] Create integration test for LLM response generation in tests/integration/test_llm_integration.py

### Implementation for User Story 1

- [X] T034 [P] [US1] Implement persona service with system prompt generation in src/services/persona_service.py
- [X] T035 [P] [US1] Implement LLM service with any-llm integration in src/services/llm_service.py
- [X] T036 [US1] Implement conversation context retrieval (sliding window, 10 message pairs) in src/services/llm_service.py
- [X] T037 [US1] Implement token estimation using tiktoken in src/services/llm_service.py
- [X] T038 [US1] Implement DM message handler in src/handlers/message_handler.py
- [X] T039 [US1] Add exponential backoff retry logic for LLM API calls in src/services/llm_service.py
- [X] T040 [US1] Add circuit breaker for LLM service using pybreaker in src/services/llm_service.py
- [X] T041 [US1] Implement fallback response selection on LLM failure in src/services/llm_service.py
- [X] T042 [US1] Add conversation session creation and management in src/handlers/message_handler.py
- [X] T043 [US1] Add message storage to database after each exchange in src/handlers/message_handler.py
- [X] T044 [US1] Register message event handler in src/bot.py
- [X] T045 [US1] Add error handling and logging for DM conversations in src/handlers/message_handler.py

**Checkpoint**: At this point, User Story 1 should be fully functional - Lukas can have contextual conversations via DM

---

## Phase 3.5: MCP Integration (Enhanced Capabilities) - COMPLETED ✅

**Goal**: Enhance Lukas with web search capabilities via Model Context Protocol to answer questions requiring current information

**Added**: 2025-10-25 | **Completed**: 2025-10-26 | **Status**: Production-ready (98% complete)

**Implementation Details**:
- Official MCP Python SDK (mcp>=1.0.0) with SSE transport
- LangChain/LangGraph create_react_agent for autonomous tool selection
- Three web search tools from web-search-mcp server
- Background task lifecycle for persistent SSE connections
- Three-tier fallback (agent → LLM → emergency response)
- Service selection via USE_MCP_AGENT env var

### Tests for MCP Integration

- [X] T105 [P] [MCP] Create unit test for MCP initialization handling in tests/unit/services/test_llm_agent_service.py
- [X] T106 [P] [MCP] Create unit test for agent fallback behavior in tests/unit/services/test_llm_agent_service.py
- [X] T107 [P] [MCP] Create unit test for token estimation in agent service in tests/unit/services/test_llm_agent_service.py
- [X] T108 [P] [MCP] Create integration test for MCP connection lifecycle in tests/integration/test_mcp_integration.py
- [X] T109 [P] [MCP] Create integration test for tool invocation flow in tests/integration/test_mcp_integration.py
- [X] T110 [P] [MCP] Create integration test for service selection logic in tests/integration/test_mcp_integration.py
- [X] T111 [P] [MCP] Create integration test for graceful degradation in tests/integration/test_mcp_integration.py

### Implementation for MCP Integration

- [X] T112 [P] [MCP] Add MCP dependencies to pyproject.toml (mcp>=1.0.0, langchain>=0.3.0, langgraph>=0.2.0, langchain-openai>=0.2.0, langchain-core>=0.3.0)
- [X] T113 [P] [MCP] Create web-search-mcp Docker container in docker/mcp-servers/web-search/Dockerfile
- [X] T114 [P] [MCP] Add web-search-mcp service to docker-compose.yml and docker-compose.dev.yml
- [X] T115 [P] [MCP] Implement LLMAgentService class in src/services/llm_agent_service.py
- [X] T116 [MCP] Implement initialize_mcp() method for MCP client setup in src/services/llm_agent_service.py
- [X] T117 [MCP] Implement _mcp_connection_lifecycle() background task for persistent SSE connection in src/services/llm_agent_service.py
- [X] T118 [MCP] Implement _create_langchain_tool() for MCP → LangChain tool conversion in src/services/llm_agent_service.py
- [X] T119 [MCP] Implement _create_agent() using create_react_agent in src/services/llm_agent_service.py
- [X] T120 [MCP] Implement _call_agent() for agent execution in src/services/llm_agent_service.py
- [X] T121 [MCP] Implement generate_response() with three-tier fallback in src/services/llm_agent_service.py
- [X] T122 [MCP] Implement cleanup() for graceful shutdown in src/services/llm_agent_service.py
- [X] T123 [MCP] Implement get_llm_service() service selection in src/handlers/message_handler.py
- [X] T124 [MCP] Add init_mcp_agent() to bot startup in src/bot.py
- [X] T125 [MCP] Add USE_MCP_AGENT environment variable to .env.example
- [X] T126 [MCP] Add MCP_WEB_SEARCH_URL environment variable to .env.example
- [X] T127 [P] [MCP] Create MCP_INTEGRATION_STATUS.md documenting implementation status
- [X] T128 [P] [MCP] Create MCP_FIX_SUMMARY.md documenting solutions and learnings
- [X] T129 [P] [MCP] Update README.md with MCP integration information
- [X] T130 [P] [MCP] Update CLAUDE.md with MCP context

**Test Results**: 12/12 tests passing (8 unit, 4 integration), 55% coverage of critical paths

**Checkpoint**: MCP integration complete - Lukas can now autonomously use web search to answer questions requiring current information

---

## Phase 4: User Story 2 - Proactive Team Engagement (Priority: P2)

**Goal**: Lukas proactively engages with the research team through random DMs and probabilistic thread responses

**Independent Test**: Configure Lukas with a 1-hour interval for random DMs and 20% thread engagement probability. Observe over a 4-hour period that Lukas sends approximately 4 random DMs to different team members and participates in roughly 20% of general channel threads. Each interaction maintains Lukas's persona.

### Tests for User Story 2

- [X] T046 [P] [US2] Create unit test for engagement probability calculation in tests/unit/test_engagement_logic.py
- [X] T047 [P] [US2] Create unit test for random DM recipient selection in tests/unit/test_engagement_service.py
- [X] T048 [P] [US2] Create integration test for scheduled task execution in tests/integration/test_scheduled_tasks.py

### Implementation for User Story 2

- [X] T049 [P] [US2] Implement engagement service with probability logic in src/services/engagement_service.py
- [X] T050 [US2] Implement random team member selection (fair distribution) in src/services/engagement_service.py
- [X] T051 [US2] Implement proactive DM message generation in src/services/engagement_service.py
- [X] T052 [US2] Implement scheduled task for random DMs in src/services/scheduler_service.py
- [X] T053 [US2] Update TeamMember.last_proactive_dm_at after sending DM in src/services/engagement_service.py
- [X] T054 [P] [US2] Implement thread monitoring handler in src/handlers/thread_handler.py
- [X] T055 [US2] Implement thread engagement decision logic in src/handlers/thread_handler.py
- [X] T056 [US2] Create EngagementEvent records for audit trail in src/handlers/thread_handler.py
- [X] T057 [US2] Implement thread context extraction for LLM prompts in src/handlers/thread_handler.py
- [X] T058 [US2] Add channel message event handler in src/bot.py
- [X] T059 [US2] Configure active hours check (pause engagement outside work hours) in src/services/engagement_service.py
- [X] T060 [US2] Add error handling for failed proactive messages in src/services/engagement_service.py
- [X] T061 [P] [US2] Implement emoji reaction selection logic in src/handlers/thread_handler.py
- [X] T062 [US2] Implement reaction posting to Slack threads via Slack API in src/handlers/thread_handler.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - Lukas can chat AND proactively engage (with both text responses and emoji reactions)

---

## Phase 5: User Story 3 - AI-Generated Bear Image Posting (Priority: P3)

**Goal**: Lukas periodically generates and posts whimsical, bear-themed images to the random channel

**Independent Test**: Configure Lukas to post an image every 24 hours. After deployment, observe that Lukas generates and posts a bear-themed image to the random channel within the expected timeframe. Images are appropriate, on-theme, and include a brief caption from Lukas.

### Tests for User Story 3

- [X] T063 [P] [US3] Create unit test for image prompt generation in tests/unit/test_image_service.py
- [X] T064 [P] [US3] Create integration test for image generation and posting in tests/integration/test_image_generation.py

### Implementation for User Story 3

- [X] T065 [P] [US3] Implement image service with DALL-E integration in src/services/image_service.py
- [X] T066 [US3] Implement contextual prompt generation (seasons, occasions) in src/services/image_service.py
- [X] T067 [US3] Implement image generation with OpenAI DALL-E 3 API in src/services/image_service.py
- [X] T068 [US3] Add prompt validation before sending to DALL-E in src/services/image_service.py
- [X] T069 [US3] Implement image upload to Slack in src/services/image_service.py
- [X] T070 [US3] Create caption generation for image posts in src/services/image_service.py
- [X] T071 [US3] Store GeneratedImage records in database in src/services/image_service.py
- [X] T072 [US3] Implement scheduled task for image posting in src/services/scheduler_service.py
- [X] T073 [US3] Add cost tracking for generated images in src/services/image_service.py
- [X] T074 [US3] Add retry logic with exponential backoff for DALL-E API in src/services/image_service.py
- [X] T075 [US3] Add error handling for content policy violations in src/services/image_service.py
- [X] T076 [US3] Implement on-demand image generation trigger for admins in src/handlers/command_handler.py

**Checkpoint**: All three user stories should now be independently functional - chat, proactive engagement, and images

---

## Phase 6: User Story 4 - Command Execution (Priority: P4)

**Goal**: Team members can issue specific commands to Lukas for administrative and utility functions

**Independent Test**: Team member sends command "Lukas, post 'Team meeting at 3pm today' to general channel". Lukas confirms understanding, posts the message to general channel, and reports completion to the requesting team member.

### Tests for User Story 4

- [X] T077 [P] [US4] Create unit test for command parsing in tests/unit/test_command_parser.py
- [X] T078 [P] [US4] Create unit test for permission checks in tests/unit/test_command_handler.py

### Implementation for User Story 4

- [X] T079 [P] [US4] Implement command parser with pattern matching in src/handlers/command_handler.py
- [X] T080 [US4] Implement "post [message] to #channel" command in src/handlers/command_handler.py
- [X] T081 [US4] Implement reminder scheduling command in src/handlers/command_handler.py
- [X] T082 [US4] Implement team information retrieval command in src/handlers/command_handler.py
- [X] T083 [US4] Implement admin configuration commands (set intervals, probabilities) in src/handlers/command_handler.py
- [X] T084 [US4] Add permission checking for admin commands in src/handlers/command_handler.py
- [X] T085 [US4] Implement command help and usage examples in src/handlers/command_handler.py
- [X] T086 [US4] Add command confirmation messages to users in src/handlers/command_handler.py
- [X] T087 [US4] Register app_mention event handler in src/bot.py
- [X] T088 [US4] Add error handling for invalid commands in src/handlers/command_handler.py
- [X] T089 [US4] Update Configuration table when settings change in src/handlers/command_handler.py

**Checkpoint**: All user stories complete - Lukas has full functionality

---

## Phase 6.5: MCP Command System Migration (Natural Language Commands) - COMPLETED ✅

**Goal**: Replace regex-based command parsing with MCP tool-based natural language command processing for improved user experience

**Added**: 2025-10-27 | **Completed**: 2025-10-27 | **Status**: Production-ready

**Implementation Details**:
- Framework-agnostic CommandService layer (shared business logic)
- Slack Operations MCP server (co-located in bot container)
- Multi-server MCP architecture (web-search + slack-operations)
- Natural language understanding via LLM agent
- 87% code reduction in command_handler.py (1340 → 180 lines)

### Tests for MCP Command System

- [X] T131 [P] [US4-MCP] Create unit test for CommandService.post_message() in tests/unit/services/test_command_service.py
- [X] T132 [P] [US4-MCP] Create unit test for CommandService.create_reminder() in tests/unit/services/test_command_service.py
- [X] T133 [P] [US4-MCP] Create unit test for CommandService.get_info() in tests/unit/services/test_command_service.py
- [X] T134 [P] [US4-MCP] Create unit test for CommandService.update_config() with permission checks in tests/unit/services/test_command_service.py
- [X] T135 [P] [US4-MCP] Create unit test for CommandService.generate_image() with permission checks in tests/unit/services/test_command_service.py
- [X] T136 [P] [US4-MCP] Create unit test for CommandService helper methods (_parse_duration_to_minutes, _parse_hours_from_string, _parse_days_from_string) in tests/unit/services/test_command_service.py
- [X] T137 [P] [US4-MCP] Create integration test for slack-operations MCP server connection in tests/integration/test_mcp_integration.py
- [X] T138 [P] [US4-MCP] Create integration test for multi-server MCP agent initialization in tests/integration/test_mcp_integration.py
- [X] T139 [P] [US4-MCP] Create integration test for tool discovery across multiple servers in tests/integration/test_mcp_integration.py

### Implementation for MCP Command System

- [X] T140 [P] [US4-MCP] Create CommandService class with framework-agnostic business logic in src/services/command_service.py
- [X] T141 [US4-MCP] Implement CommandService.post_message() method in src/services/command_service.py
- [X] T142 [US4-MCP] Implement CommandService.create_reminder() with time parsing in src/services/command_service.py
- [X] T143 [US4-MCP] Implement CommandService.get_info() supporting team/status/stats in src/services/command_service.py
- [X] T144 [US4-MCP] Implement CommandService.update_config() with admin permission check in src/services/command_service.py
- [X] T145 [US4-MCP] Implement CommandService.generate_image() with admin permission check in src/services/command_service.py
- [X] T146 [P] [US4-MCP] Add starlette and uvicorn dependencies to pyproject.toml
- [X] T147 [P] [US4-MCP] Create MCP server with 5 Slack operation tools in src/mcp_server.py
- [X] T148 [US4-MCP] Implement post_message_to_channel tool in src/mcp_server.py
- [X] T149 [US4-MCP] Implement create_reminder tool in src/mcp_server.py
- [X] T150 [US4-MCP] Implement get_team_info tool in src/mcp_server.py
- [X] T151 [US4-MCP] Implement update_bot_config tool in src/mcp_server.py
- [X] T152 [US4-MCP] Implement generate_and_post_image tool in src/mcp_server.py
- [X] T153 [P] [US4-MCP] Create multi-process startup script in docker/start-bot.sh
- [X] T154 [US4-MCP] Update Dockerfile to use start-bot.sh entrypoint in docker/Dockerfile
- [X] T155 [P] [US4-MCP] Add MCP_SLACK_OPS_URL environment variable to docker-compose.dev.yml
- [X] T156 [P] [US4-MCP] Expose port 9766 for MCP server in docker-compose.dev.yml
- [X] T157 [US4-MCP] Update llm_agent_service.py to support multiple MCP servers in src/services/llm_agent_service.py
- [X] T158 [US4-MCP] Update initialize_mcp() to connect to slack-operations server in src/services/llm_agent_service.py
- [X] T159 [US4-MCP] Simplify command_handler.py to route all mentions to LLM agent in src/handlers/command_handler.py
- [X] T160 [US4-MCP] Remove CommandParser class from command_handler.py
- [X] T161 [US4-MCP] Remove CommandExecutor implementation from command_handler.py
- [X] T162 [P] [US4-MCP] Create MCP_COMMAND_MIGRATION_COMPLETE.md documentation
- [X] T163 [P] [US4-MCP] Update spec.md to reflect natural language command processing
- [X] T164 [P] [US4-MCP] Update plan.md with MCP command system architecture
- [X] T165 [P] [US4-MCP] Update tasks.md with completed command migration tasks

**Test Results**: 16 unit tests + 7 integration tests = 23 total (21 passing, 2 skipped for live server)

**Benefits**:
- Natural language flexibility (multiple phrasings work)
- 87% code reduction in command handler
- Zero code duplication (CommandService shared layer)
- Framework-agnostic testing
- Improved maintainability

**Checkpoint**: Command system migrated to MCP - users can now use natural language instead of exact command syntax

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and deployment readiness

- [ ] T090 [P] Implement data cleanup scheduled task (90-day retention) in src/services/scheduler_service.py
- [ ] T091 [P] Create database backup documentation in quickstart.md
- [ ] T092 [P] Add comprehensive error logging across all services
- [ ] T093 [P] Implement Slack API rate limit handling in all handlers
- [ ] T094 Create Docker entrypoint script that runs Alembic migrations in docker/entrypoint.sh
- [ ] T095 [P] Add health check endpoint for monitoring (future enhancement placeholder)
- [ ] T096 [P] Optimize database indexes based on query patterns
- [ ] T097 [P] Add SQLite WAL mode configuration in src/utils/database.py
- [ ] T098 Test full deployment using docker-compose up
- [ ] T099 Validate all quickstart.md setup steps
- [ ] T100 [P] Add admin notification for critical errors
- [ ] T101 [P] Document all environment variables in .env.example
- [ ] T102 Run ruff linter and fix code style issues across all files
- [ ] T103 Update README.md with final usage instructions and examples
- [ ] T104 Create initial CHANGELOG.md entry for v0.1.0 release

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses US1's LLM service but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Completely independent of US1/US2
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - May trigger US2/US3 functionality but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services (already in Foundational phase)
- Services before handlers
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**: T003, T004, T005, T006, T007, T008, T010, T011 can all run in parallel

**Phase 2 (Foundational)**: T013-T021 (all models), T023-T025 (repositories), T026 can run in parallel

**User Story 1**: T030-T033 (all tests), T034-T035 can run in parallel

**User Story 2**: T046-T048 (all tests), T049, T054 can start in parallel

**User Story 3**: T061-T062 (tests), T063 can start immediately after foundational

**User Story 4**: T075-T076 (tests), T077 can start immediately after foundational

**Phase 7 (Polish)**: T088-T091, T093-T095, T098-T099 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create unit test for persona prompt generation in tests/unit/test_persona_service.py"
Task: "Create unit test for conversation context building in tests/unit/test_llm_service.py"
Task: "Create integration test for DM message handling in tests/integration/test_slack_events.py"
Task: "Create integration test for LLM response generation in tests/integration/test_llm_integration.py"

# Launch both services together:
Task: "Implement persona service with system prompt generation in src/services/persona_service.py"
Task: "Implement LLM service with any-llm integration in src/services/llm_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T011)
2. Complete Phase 2: Foundational (T012-T029) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T030-T045)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo basic chatbot with direct conversation capability

**This is the recommended MVP** - delivers immediate value with team members able to chat with Lukas.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (proactive engagement)
4. Add User Story 3 → Test independently → Deploy/Demo (image posting)
5. Add User Story 4 → Test independently → Deploy/Demo (full featured)
6. Complete Phase 7 → Production ready

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T029)
2. Once Foundational is done:
   - Developer A: User Story 1 (T030-T045)
   - Developer B: User Story 2 (T046-T062)
   - Developer C: User Story 3 (T063-T076)
   - Developer D: User Story 4 (T077-T089)
3. Stories complete and integrate independently
4. Team completes Polish together (T090-T104)

---

## Task Summary

**Total Tasks**: 165 tasks

**Task Count by Phase**:
- Phase 1 (Setup): 11 tasks ✅
- Phase 2 (Foundational): 18 tasks ✅
- Phase 3 (User Story 1 - Direct Conversation): 16 tasks ✅
- Phase 3.5 (MCP Integration): 26 tasks ✅ (COMPLETED)
- Phase 4 (User Story 2 - Proactive Engagement): 17 tasks ✅
- Phase 5 (User Story 3 - Image Posting): 14 tasks ✅ (COMPLETED)
- Phase 6 (User Story 4 - Commands): 13 tasks ✅ (COMPLETED)
- Phase 6.5 (MCP Command System Migration): 35 tasks ✅ (COMPLETED)
- Phase 7 (Polish): 15 tasks

**Parallel Opportunities**: 35+ tasks marked [P] can run in parallel within their phases

**Independent Test Criteria**:
- US1: Send DM, receive contextual response within 5s
- US2: Observe random DMs and thread engagement over 4-hour period
- US3: Observe scheduled image post with appropriate theme
- US4: Send command, verify execution and confirmation

**Suggested MVP Scope**: Phases 1-3 (Setup + Foundational + User Story 1) = 45 tasks

**Estimated Implementation Time**:
- MVP (US1 only): 1 week (1 developer, part-time)
- Full feature (US1-US4): 3-4 weeks (1 developer, part-time)
- With parallel team: 1-2 weeks (4 developers)

---

## Format Validation

✅ All tasks follow checklist format: `- [ ] [TaskID] [P?] [Story?] Description`
✅ All task IDs sequential (T001-T104)
✅ All user story tasks labeled with [US1], [US2], [US3], or [US4]
✅ All tasks include specific file paths
✅ Setup and Foundational tasks have NO story labels
✅ Polish tasks have NO story labels
✅ Parallelizable tasks marked with [P]

---

## Notes

- Tests follow 80/20 rule: focusing on critical paths (DM handling, LLM integration, engagement logic, command parsing)
- Each user story is independently testable and deliverable
- Tasks within stories ordered by dependency (tests first, then models/services, then handlers)
- [P] tasks target different files with no shared dependencies
- MVP delivers core value (conversational AI) in minimal scope
- Incremental delivery allows validation at each user story completion
- Constitution compliance: Simple architecture, pragmatic testing, documented decisions
