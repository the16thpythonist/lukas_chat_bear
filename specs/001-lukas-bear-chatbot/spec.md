# Feature Specification: Lukas the Bear Slack Chatbot

**Feature Branch**: `001-lukas-bear-chatbot`
**Created**: 2025-10-24
**Status**: Draft
**Input**: User description: "Build a slack chatbot application which assumes the persona of 'Lukas the Bear' which is a stuffed animal and our office mascot. This chatbot is supposed to be integrated into the Slack channel of our research team. The bot is supposed to perform certain tasks: Message random team members in a fixed interval, React to or answer threads in the general channel with a certain probability, Occasionally post generated pictures into the random channel, Be available for people to chat with, Be able to perform certain requests on prompting."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Direct Conversation with Lukas (Priority: P1)

Team members can initiate direct message conversations with Lukas the Bear to chat, ask questions, or request information. Lukas responds with the personality of a friendly stuffed bear mascot, providing engaging and contextual responses while maintaining awareness of the research team's context.

**Why this priority**: Core chatbot functionality that delivers immediate value. Even without proactive features, team members can interact with Lukas for information, entertainment, and team building. This is the foundation upon which all other features build.

**Independent Test**: Team member can send a direct message to Lukas asking "What's the weather like today?" and receive a personality-driven response. Can also ask about team information, meeting schedules, or general questions and get relevant answers.

**Acceptance Scenarios**:

1. **Given** team member opens DM with Lukas, **When** they send "Hi Lukas, how are you?", **Then** Lukas responds within 5 seconds with a bear-themed greeting reflecting his persona
2. **Given** team member asks Lukas "Who's working on project X?", **When** message is sent, **Then** Lukas retrieves and shares team information in a friendly manner
3. **Given** ongoing conversation with context, **When** team member asks follow-up question, **Then** Lukas maintains conversation context and provides relevant response
4. **Given** team member sends unclear or ambiguous message, **When** Lukas cannot determine intent, **Then** Lukas asks for clarification in a friendly, helpful way
5. **Given** multiple team members chatting simultaneously, **When** each sends messages, **Then** each receives individual responses maintaining separate conversation contexts

---

### User Story 2 - Proactive Team Engagement (Priority: P2)

Lukas proactively engages with the research team through two mechanisms: (1) sending random direct messages to individual team members at configured intervals to check in, share encouragement, or start conversations, and (2) monitoring the general channel and randomly responding to or reacting to thread discussions with contextually relevant input.

**Why this priority**: Transforms Lukas from a reactive bot to an active team presence. Increases team engagement, fosters spontaneous interactions, and makes Lukas feel like a genuine member of the team rather than just a tool.

**Independent Test**: Configure Lukas with a 1-hour interval for random DMs and 20% thread engagement probability. Observe over a 4-hour period that Lukas sends approximately 4 random DMs to different team members and participates in roughly 20% of general channel threads. Each interaction maintains Lukas's persona.

**Acceptance Scenarios**:

1. **Given** random DM interval is set to 2 hours, **When** 2 hours elapse, **Then** Lukas sends a friendly message to a randomly selected team member
2. **Given** someone posts a new thread in general channel, **When** Lukas evaluates the thread, **Then** Lukas responds or reacts based on configured probability (e.g., 15-25%)
3. **Given** Lukas sends a proactive DM, **When** team member responds, **Then** Lukas engages in natural back-and-forth conversation
4. **Given** thread in general channel discusses research topics, **When** Lukas decides to engage, **Then** Lukas adds relevant, contextual commentary in his bear persona
5. **Given** same team member was contacted recently, **When** selecting next random DM recipient, **Then** Lukas prioritizes team members not recently contacted
6. **Given** general channel thread is already very active, **When** Lukas evaluates engagement, **Then** Lukas avoids overwhelming busy threads

---

### User Story 3 - AI-Generated Bear Image Posting (Priority: P3)

Lukas periodically generates and posts whimsical, bear-themed images to the random channel. These images reflect Lukas's personality and current events, seasons, or team milestones, creating visual engagement and entertainment for the team.

**Why this priority**: Adds visual personality and entertainment value beyond text interactions. Reinforces Lukas's identity as the team mascot and creates shareable moments that boost team morale.

**Independent Test**: Configure Lukas to post an image every 24 hours. After deployment, observe that Lukas generates and posts a bear-themed image to the random channel within the expected timeframe. Images are appropriate, on-theme, and include a brief caption from Lukas.

**Acceptance Scenarios**:

1. **Given** image posting interval is set to 24 hours, **When** interval elapses, **Then** Lukas generates a new bear-themed image and posts it to random channel with caption
2. **Given** it's a holiday or special occasion, **When** generating image, **Then** Lukas incorporates seasonal or occasion-specific themes
3. **Given** team recently achieved a milestone, **When** prompted by admin, **Then** Lukas can generate celebratory bear image on demand
4. **Given** image generation fails, **When** error occurs, **Then** Lukas logs error and retries later without posting broken content
5. **Given** generated image is posted, **When** team members react or comment, **Then** Lukas can respond to comments about the image

---

### User Story 4 - Natural Language Command Execution (Priority: P4)

Team members can issue commands to Lukas using natural language for administrative and utility functions. Lukas uses AI to understand intent and execute commands including: posting announcements to channels, creating reminders, retrieving team information, and administrative configuration of behavior (intervals, probabilities, persona adjustments). Commands are processed through MCP (Model Context Protocol) tools, allowing flexible natural language rather than rigid syntax.

**Why this priority**: Extends Lukas beyond conversation to become a useful team utility. Natural language command processing eliminates the need to learn specific command syntax, making Lukas more accessible and user-friendly while maintaining the bear mascot personality.

**Independent Test**: Team member sends "Hey Lukas, can you post 'Team meeting at 3pm today' to the general channel?". Lukas understands the intent, posts the message to general channel, and confirms completion. Alternative phrasings like "send a message to #general saying..." or "announce to the team that..." also work.

**Acceptance Scenarios**:

1. **Given** team member says "Lukas, post [message] to #general" OR "send a message to the team saying..." OR "announce in #general that...", **When** LLM processes request, **Then** Lukas uses post_message_to_channel tool, posts message, and confirms action
2. **Given** team member asks "remind me in 30 minutes to check the build" OR "ping me in half an hour about the build" OR "can you remind me tomorrow at 3pm", **When** request is processed, **Then** Lukas uses create_reminder tool and confirms scheduled reminder
3. **Given** admin says "set random DM interval to 4 hours" OR "change the DM frequency to every 4 hours" OR "update dm interval to 4h", **When** command is processed, **Then** Lukas uses update_bot_config tool and confirms configuration change
4. **Given** team member asks "who's on the team?" OR "team info" OR "show me the team member list", **When** request is processed, **Then** Lukas uses get_team_info tool and shares team information
5. **Given** unauthorized user tries admin command, **When** MCP tool enforces permission check, **Then** Lukas politely declines and explains admin-only restriction
6. **Given** ambiguous request is received, **When** LLM cannot determine clear intent, **Then** Lukas asks for clarification in a friendly, helpful way

---

### Edge Cases

- What happens when Slack API rate limits are reached during high activity?
- How does Lukas handle multiple simultaneous conversations while maintaining distinct contexts?
- What happens if image generation service is unavailable or returns inappropriate content?
- How does Lukas behave during team off-hours (nights, weekends) - should proactive engagement pause?
- What happens when a team member leaves the organization but Lukas has scheduled a DM?
- How does Lukas handle message threads that become heated or controversial?
- What happens if LLM API returns an error or timeout during conversation?
- How does Lukas handle mentions in channels it's not configured to monitor?
- What happens when conversation history becomes very long and exceeds context limits?
- How does Lukas respond to spam or abusive messages?

## Requirements *(mandatory)*

### Functional Requirements

**Core Chatbot Capabilities**

- **FR-001**: System MUST respond to direct messages with conversational responses maintaining Lukas the Bear's persona (friendly, helpful stuffed animal mascot)
- **FR-002**: System MUST maintain separate conversation contexts for each team member to enable coherent multi-turn conversations
- **FR-003**: System MUST process natural language queries using LLM integration to understand user intent and generate appropriate responses
- **FR-004**: System MUST respond to direct messages within 5 seconds under normal load conditions
- **FR-005**: System MUST maintain conversation history for contextual awareness within ongoing conversations

**Proactive Engagement**

- **FR-006**: System MUST send direct messages to randomly selected team members at configurable intervals (default: every 24-48 hours)
- **FR-007**: System MUST track which team members were recently contacted to ensure fair distribution of proactive messages
- **FR-008**: System MUST monitor designated channels (default: general channel) for new threads and messages
- **FR-009**: System MUST probabilistically engage with threads based on configurable probability (default: 15-25%)
- **FR-010**: System MUST generate contextually relevant responses when engaging with channel threads
- **FR-011**: System MUST support pause/resume functionality for proactive features during specified hours or dates

**Image Generation & Posting**

- **FR-012**: System MUST generate bear-themed images using AI image generation service at configurable intervals (default: once per week)
- **FR-013**: System MUST post generated images to designated channel (default: random channel) with Lukas-persona captions
- **FR-014**: System MUST support on-demand image generation when prompted by authorized users
- **FR-015**: System MUST incorporate contextual themes (seasons, holidays, milestones) into image generation prompts
- **FR-016**: System MUST validate generated images before posting to prevent inappropriate content

**Natural Language Command Processing (MCP-Based)**

- **FR-017**: System MUST understand natural language command requests using LLM agent with MCP tools (e.g., "post this to #channel", "send a message to the team", "announce in #general")
- **FR-018**: System MUST support scheduled reminders via create_reminder tool accepting flexible time formats ("30 minutes", "2 hours", "3pm", "tomorrow at 9am")
- **FR-019**: System MUST provide team information retrieval via get_team_info tool (team members, bot status, engagement statistics)
- **FR-020**: System MUST allow authorized administrators to configure bot behavior via update_bot_config tool (intervals, probabilities, settings)
- **FR-021**: System MUST enforce permission checks for administrative commands within MCP tool execution (admin-only tools return permission denied for non-admins)
- **FR-022**: System MUST understand command intent across multiple natural language phrasings without requiring exact syntax

**Slack Integration**

- **FR-023**: System MUST authenticate with Slack workspace using appropriate bot token scopes
- **FR-024**: System MUST listen to Slack events (direct messages, mentions, thread activity) in real-time
- **FR-025**: System MUST send messages, post images, and add reactions through Slack API
- **FR-026**: System MUST handle Slack API rate limiting gracefully with exponential backoff
- **FR-027**: System MUST maintain Slack workspace member roster for targeting and context

**Enhanced Capabilities (MCP Integration)**

- **FR-034**: System MUST integrate web search capabilities via Model Context Protocol (MCP) using official MCP Python SDK with SSE transport
- **FR-035**: System MUST provide three web search tools via web-search-mcp server: full-web-search (complete content), get-web-search-summaries (snippets only), get-single-web-page-content (specific URL extraction)
- **FR-036**: System MUST use LangChain/LangGraph agent framework with create_react_agent to autonomously decide when tools are needed (both web search and command execution)
- **FR-037**: System MUST maintain personality and conversation context when using tool capabilities
- **FR-038**: System MUST gracefully degrade to standard conversation mode if MCP servers are unavailable (three-tier fallback: agent with tools → direct LLM → emergency persona response)
- **FR-039**: System MUST support background task lifecycle for MCP connections to maintain persistent SSE context throughout bot lifetime
- **FR-040**: System MUST support configuration toggle (USE_MCP_AGENT env var) to enable/disable MCP agent service
- **FR-041**: System MUST connect to multiple MCP servers (web-search-mcp, slack-operations-mcp) via Docker network or localhost using SSE endpoints at startup
- **FR-042**: System MUST run slack-operations MCP server as co-located process within same container (multi-process architecture)
- **FR-043**: System MUST expose five Slack operation tools via slack-operations-mcp: post_message_to_channel, create_reminder, get_team_info, update_bot_config (admin-only), generate_and_post_image (admin-only)
- **FR-044**: System MUST share CommandService business logic layer between Slack handlers and MCP server for code reuse
- **FR-045**: System MUST enforce permission checks within MCP tools (admin-only tools verify user.is_admin before execution)
- **FR-046**: System MUST run MCP server on configurable port (default: 9766) with SSE endpoint at /sse
- **FR-047**: System MUST handle MCP server startup/shutdown gracefully with main bot process (startup script manages both processes)

**Reliability & Error Handling**

- **FR-028**: System MUST log all interactions, errors, and system events for debugging and monitoring
- **FR-029**: System MUST gracefully handle LLM API failures with fallback responses
- **FR-030**: System MUST retry failed operations with exponential backoff
- **FR-031**: System MUST continue operating when individual features fail (e.g., image generation down doesn't break chat)
- **FR-032**: System MUST detect and filter inappropriate or policy-violating content before posting
- **FR-033**: System MUST persist conversation state and configuration to survive restarts

### Key Entities

- **Conversation Session**: Represents an ongoing dialogue between Lukas and a team member. Contains message history, context, participant information, and session metadata. Each session is isolated to maintain coherent conversations.

- **Team Member**: Represents a Slack workspace user. Contains user ID, display name, recent interaction timestamps, preference settings, and authorization level (normal user vs. admin).

- **Scheduled Task**: Represents a time-based action (random DM, image post, reminder). Contains task type, execution time, target (channel or user), configuration parameters, and execution status.

- **Engagement Event**: Represents Lukas's interaction with a channel thread. Contains thread ID, channel, engagement decision (respond/react/ignore), probability used, and outcome.

- **Command**: Represents a parsed user request. Contains command type, parameters, requesting user, target channel/user, and authorization requirements.

- **Configuration**: Represents system settings. Contains intervals for proactive actions, engagement probabilities, persona parameters, active hours, authorized administrators, and channel assignments.

- **Generated Image**: Represents an AI-generated image post. Contains generation timestamp, prompt used, target channel, image metadata, and posting status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Responsiveness**

- **SC-001**: Team members receive responses to direct messages within 5 seconds for 95% of interactions
- **SC-002**: System maintains 99% uptime during business hours (Mon-Fri, 8am-6pm)

**Engagement**

- **SC-003**: Each team member receives at least one proactive direct message from Lukas per month
- **SC-004**: Lukas participates in 15-25% of general channel threads as measured over one week period
- **SC-005**: Generated images receive average of 3+ reactions from team members
- **SC-006**: At least 70% of team members interact with Lukas (send at least one message) within first month

**Functionality**

- **SC-007**: Commands execute successfully with 95% success rate (excluding user errors)
- **SC-008**: Image generation and posting completes successfully 90% of scheduled attempts
- **SC-009**: System handles up to 10 simultaneous conversations without degradation

**Quality**

- **SC-010**: Lukas's responses are rated as "on-brand" (maintaining bear persona) by team members 90% of the time in spot checks
- **SC-011**: Zero inappropriate or policy-violating content posted by Lukas (manual or automated filtering catches all issues)
- **SC-012**: Conversation context is maintained correctly across multi-turn dialogues 95% of the time

**Team Impact**

- **SC-013**: Team reports increased sense of community and fun in post-deployment survey
- **SC-014**: Lukas-facilitated reminders and announcements reach intended audiences 100% of the time
- **SC-015**: Administrative overhead for managing Lukas is under 30 minutes per week

## Assumptions

- Slack workspace has appropriate bot integration permissions enabled
- Team size is small to medium (under 50 members) for effective random engagement distribution
- LLM API service (OpenAI, Anthropic, or similar) is available with appropriate rate limits and budget
- AI image generation service (DALL-E, Midjourney, Stable Diffusion) is available with API access
- Team members understand Lukas is a bot and are receptive to automated mascot interactions
- Research team operates primarily during standard business hours in a single timezone
- Appropriate budget allocated for LLM and image generation API costs
- Administrative access to Slack workspace for bot setup and permissions configuration
- Team communication culture is informal enough to appreciate mascot bot personality

## Out of Scope

- Poll creation and management - may be added in future iterations
- Integration with external project management tools (Jira, Asana, etc.) - may be added in future iterations
- Voice or video call capabilities - text-only interaction
- Multi-workspace deployment - single Slack workspace only for initial version
- Mobile app or standalone interface - Slack-only interaction
- Custom AI model training - uses existing LLM and image generation APIs
- Automated content moderation learning - manual configuration of content filters
- Multi-language support - English only for initial version
- Analytics dashboard - basic logging only, no visualization interface
- Lukas persona customization by individual users - single shared persona
- Integration with calendar systems for automatic meeting awareness

## Technical Enhancements

**Model Context Protocol (MCP) Integration**: The system integrates the official MCP Python SDK (mcp>=1.0.0) with LangChain/LangGraph to enable tool-augmented conversations. This allows Lukas to autonomously access both web search capabilities and Slack command execution when helpful, using natural language instead of rigid command syntax.

**Multi-Server MCP Architecture**:
- **web-search-mcp**: External container providing web search capabilities (Node.js + Playwright browsers)
- **slack-operations-mcp**: Co-located MCP server running in same container as bot (Python + Starlette + Uvicorn)
- **Agent Framework**: LangChain's create_react_agent autonomously selects appropriate tools based on user intent
- **Connection Management**: Multiple persistent SSE connections maintained via background tasks throughout bot lifetime

**Web Search Tools** (via web-search-mcp server):
- `full-web-search`: Complete web search with full page content extraction
- `get-web-search-summaries`: Lightweight search returning snippets only
- `get-single-web-page-content`: Extract content from specific URLs

**Slack Operation Tools** (via slack-operations-mcp server):
- `post_message_to_channel`: Post messages to Slack channels (public)
- `create_reminder`: Schedule reminders for users (public)
- `get_team_info`: Retrieve team information, bot status, or engagement statistics (public)
- `update_bot_config`: Update bot configuration settings (admin-only)
- `generate_and_post_image`: Generate and post AI images (admin-only)

**Command System Architecture**:
- **CommandService Layer**: Pure business logic shared between Slack handlers and MCP server (src/services/command_service.py)
- **MCP Server**: Exposes CommandService methods as MCP tools (src/mcp_server.py, runs on port 9766)
- **Multi-Process Container**: Startup script (docker/start-bot.sh) launches both MCP server (background) and Slack bot (foreground)
- **Code Reuse**: Zero duplication - CommandService handles all business logic, MCP server provides protocol translation
- **Natural Language**: Replaces 1,100+ lines of regex command parsing with LLM intent understanding

**Implementation Details**:
- **MCP SDK**: Official Python MCP client and server with SSE transport
- **Web Framework**: Starlette + Uvicorn for MCP server HTTP/SSE endpoints
- **Multi-Server Support**: LLM agent connects to multiple MCP servers, combines all tools
- **Service Selection**: `get_llm_service()` selects MCP-enabled agent (if available) or standard LLM based on USE_MCP_AGENT env var
- **Graceful Degradation**: Three-tier fallback ensures responses always generated:
  1. Try agent with MCP tools (web search + Slack operations)
  2. If agent fails → Try direct LLM without tools
  3. If LLM fails → Use emergency persona fallback response
- **Permission Enforcement**: MCP tools enforce permission checks (admin-only tools verify user.is_admin)
- **Testing**: 23 tests (16 CommandService unit, 5 MCP integration, 2 live/skipped) with 100% pass rate
- **Performance**:
  - MCP server startup: ~3s
  - Command execution via MCP: ~800-1200ms (includes LLM inference)
  - Web search via MCP: ~3-10s
  - Overall response: <15s
- **Resource Usage**:
  - web-search-mcp container: +500MB-2GB (browsers + Node.js)
  - slack-operations-mcp: +50MB (Python + Starlette, same container)

**Benefits Over Regex Parsing**:
- **User Experience**: Natural language ("remind me in 30 mins") vs exact syntax ("remind me in 30 minutes to")
- **Flexibility**: Multiple phrasings work ("post this to #channel", "send message to channel", "announce in channel")
- **Maintainability**: Add new commands by updating tool descriptions, not regex patterns
- **Code Quality**: 74% test coverage, ~1,100 fewer lines of regex parsing code
- **Architecture**: Clean separation (business logic, MCP protocol, Slack protocol)

The integration is production-ready with comprehensive error handling, monitoring, and documentation. If MCP servers are unavailable, Lukas continues operating with standard LLM capabilities, ensuring uninterrupted service.
