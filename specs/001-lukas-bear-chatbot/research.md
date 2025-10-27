# Technical Research: Lukas the Bear Slack Chatbot

**Date**: 2025-10-24
**Feature**: Lukas the Bear Slack Chatbot
**Purpose**: Resolve technical uncertainties and document technology choices

## Research Questions

From Technical Context, we identified four areas needing clarification:
1. Image Generation service selection
2. Task Scheduling library choice
3. LLM Context Management strategy
4. Error Recovery patterns

---

## 1. Image Generation Service

### Decision: DALL-E 3 via OpenAI API

**Rationale**:
- **Accessibility**: Most straightforward API integration with Python SDK
- **Quality**: DALL-E 3 produces high-quality, appropriate images with good prompt adherence
- **Safety**: Built-in content moderation prevents inappropriate image generation
- **Cost**: Reasonable pricing ($0.040-0.080 per image) for low-volume use case (~1 image/week)
- **Reliability**: OpenAI's infrastructure provides consistent uptime

**Alternatives Considered**:

| Service | Pros | Cons | Why Rejected |
|---------|------|------|--------------|
| Stable Diffusion (Stability AI) | Lower cost, more customization | Requires more complex prompt engineering, less consistent quality | Image quality and simplicity not worth cost savings for low-volume use |
| Midjourney | Exceptional quality | No official API (only Discord bot), harder to automate | API access limitation makes it impractical for automated posting |
| Local Stable Diffusion | No API costs | Requires GPU, more complex Docker setup, maintenance overhead | Adds infrastructure complexity not justified by 1 image/week usage |

**Implementation Notes**:
- Use `openai` Python package (official SDK)
- Generate images with size 1024x1024 (standard DALL-E 3 output)
- Store prompt templates in `config/persona_prompts.yml` for bear-themed variations
- Implement retry logic for transient API failures
- Cache generated image URLs in database to avoid regeneration on posting failures

---

## 2. Task Scheduling

### Decision: APScheduler (Advanced Python Scheduler)

**Rationale**:
- **Simplicity**: Runs in-process, no additional infrastructure required
- **Sufficient Features**: Supports cron-style and interval-based scheduling
- **Persistence**: Can persist jobs to database (SQLite) to survive restarts
- **Lightweight**: No broker/worker overhead for our single-instance deployment
- **Scale Match**: Perfect for <50 users, hundreds of tasks per day

**Alternatives Considered**:

| Library | Pros | Cons | Why Rejected |
|---------|------|------|--------------|
| Celery | Industry standard, highly scalable | Requires Redis/RabbitMQ broker, significant complexity overhead | Over-engineered for single-instance, single-workspace deployment |
| Python `schedule` | Very simple | No persistence, no timezone support, runs in main thread | Lacks persistence needed for reliable proactive messaging |
| Cron + separate script | Standard Unix tool | Separate process, harder to coordinate with main app state | Complicates deployment, can't access app's database connection easily |

**Implementation Notes**:
- Use `BackgroundScheduler` to run jobs in background threads
- Configure `SQLAlchemyJobStore` to persist scheduled tasks to SQLite
- Schedule types needed:
  - **Interval jobs**: Random DM every 24-48 hours (configurable)
  - **Interval jobs**: Image posting weekly (configurable)
  - **Cron jobs**: Daily cleanup of old conversation history (retention policy)
- Handle missed jobs gracefully (if bot was down during scheduled time)
- Store job metadata in our `ScheduledTask` model for audit trail

---

## 3. LLM Context Management

### Decision: Sliding Window with Token-Based Truncation

**Rationale**:
- **LLM Context Window Limitations**: Most LLMs have context windows (4k-32k tokens typically)
- **Conversation Quality**: Recent messages more relevant than old ones
- **Cost Optimization**: Fewer tokens per request = lower API costs
- **Practical Limit**: Conversations rarely exceed 20 turns before context reset is natural

**Strategy**:

1. **Store Full History**: Persist all messages in database for audit/analysis
2. **Sliding Window**: Only send last N messages to LLM
   - Initial limit: Last 10 message pairs (20 messages total)
   - Configurable via `config.yml`
3. **Token-Based Truncation**: If 10 pairs exceed token limit (estimate 4k tokens)
   - Trim oldest messages first
   - Always include system prompt (persona definition)
   - Keep at minimum last 2-3 message pairs for coherence
4. **Smart Summarization** (Phase 2 enhancement - out of scope for MVP):
   - For very long conversations, summarize older context
   - Not implemented initially per YAGNI principle

**Implementation Notes**:
- Calculate approximate token count using `tiktoken` library (OpenAI tokenizer)
- Store token count metadata with each conversation session
- Log when truncation occurs for monitoring/tuning
- Document truncation behavior in user-facing documentation (rare edge case)

**any-llm Integration**:
- `any-llm` (https://github.com/mozilla-ai/any-llm) provides unified Python interface across LLM providers
- Acts as abstraction layer over OpenAI, Anthropic, Cohere, HuggingFace, and local models
- Use any-llm's chat completion interface with conversation history
- Benefits:
  - Switch LLM providers without code changes (just config)
  - Consistent message format across providers
  - Built-in retry and error handling
  - Cost tracking across providers
- Store provider type and model name in configuration for debugging
- Format messages as list of dicts: `[{"role": "system/user/assistant", "content": "..."}]`

---

## 4. Error Recovery Patterns

### Decision: Exponential Backoff with Circuit Breaker + Graceful Degradation

**Rationale**:
- **Transient Failures**: Slack/LLM APIs may have temporary network/rate-limit issues
- **User Experience**: Bot should remain responsive even when external services fail
- **Rate Limits**: Aggressive retries can worsen rate limiting problems
- **Partial Availability**: Some features failing shouldn't break entire bot

**Patterns Implemented**:

### 4.1 Exponential Backoff (for transient failures)
```text
Retry attempts: 3 max
Initial delay: 1 second
Backoff multiplier: 2x
Max delay: 10 seconds

Example: 1s → 2s → 4s → give up
```

**Use Cases**:
- Slack API calls (rate limits, network hiccups)
- LLM API calls (timeouts, temporary overload)
- Image generation API (processing delays)

**Implementation**: `tenacity` Python library with decorator pattern

### 4.2 Circuit Breaker (for sustained failures)
```text
Failure threshold: 5 consecutive failures
Open duration: 60 seconds
Half-open test: Single retry after duration
```

**Use Cases**:
- LLM service completely down
- Image generation API outage
- Database connection issues

**Implementation**: `pybreaker` library wrapping external service calls

### 4.3 Graceful Degradation (feature fallbacks)

| Feature | Failure Scenario | Degraded Behavior |
|---------|------------------|-------------------|
| LLM Conversation | API unavailable | Return pre-defined friendly fallback responses ("I'm having trouble thinking right now, try again in a moment!") |
| Image Generation | API failure | Skip posting, reschedule for next interval, log for admin notification |
| Proactive DM | Scheduling error | Log error, continue with next scheduled task, don't block other features |
| Command Execution | Parse failure | Ask user for clarification, suggest command format examples |
| Thread Engagement | Channel access error | Skip engagement attempt, log for permission troubleshooting |

**Implementation Notes**:
- Fallback responses stored in `config/persona_prompts.yml`
- All degraded states logged with ERROR level for monitoring
- Health check endpoint (future enhancement) reports feature status
- Failed image generation attempts logged to database for retry/debugging

### 4.4 Rate Limit Handling

**Slack API Rate Limits**:
- Tier 3 (most methods): 50+ req/minute
- Message posting: 1+ message/second per channel
- Strategy: Built-in rate limiting in Slack Bolt SDK respects 429 responses

**LLM API Rate Limits** (varies by provider via any-llm):
- OpenAI: Tier-based (typical: 90k tokens/min for GPT-3.5)
- Strategy: Queue requests, implement exponential backoff on 429s
- Fallback: If consistently hitting limits, return "I'm a bit overwhelmed" response

**Image Generation Rate Limits**:
- DALL-E: 5 images/minute (sufficient for 1 image/week)
- Strategy: No special handling needed at current volume
- Future: Implement request queue if scaling up

---

## 5. Supporting Research

### 5.1 Slack Bolt SDK Best Practices

**Event Handling**:
- Use `@app.event` decorators for clean event routing
- Separate handlers by event type for maintainability
- Acknowledge events within 3 seconds (use `ack()`)
- Offload long-running tasks (LLM calls) to background threads via `@app.lazy`

**Message Threading**:
- Track `thread_ts` to maintain conversation context in channels
- Use `thread_ts` in database to group related messages

**Bot Permissions Needed** (OAuth scopes):
- `channels:history` - Read general channel messages
- `channels:read` - List channels
- `chat:write` - Post messages
- `im:history` - Read DMs
- `im:write` - Send DMs
- `users:read` - Get team member info
- `files:write` - Post images
- `reactions:write` - Add emoji reactions

**Socket Mode vs Events API**:
- **Decision**: Socket Mode for initial deployment
- **Rationale**: Simpler setup, no public webhook endpoint required
- **Trade-off**: Requires WebSocket connection, but acceptable for single-instance deployment
- **Future**: Switch to Events API if needing multiple instances

### 5.2 SQLAlchemy with SQLite

**Schema Design**:
- Use `sqlalchemy.orm` for model definitions
- Alembic for schema migrations
- SQLite sufficient for estimated load (<500 messages/day, <50 users)

**Connection Pooling**:
- SQLite limitation: Single writer at a time
- Mitigation: Use `check_same_thread=False` for multi-threaded access
- Alternative considered: PostgreSQL (rejected due to deployment complexity for small scale)

**Data Retention**:
- Keep conversation history for 90 days (configurable)
- Archive old conversations to JSON files (future enhancement)
- Use APScheduler cron job for daily cleanup

### 5.3 Docker Compose Architecture

**Services**:
```yaml
services:
  lukas-bot:
    build: ./docker
    volumes:
      - ./data:/app/data  # SQLite database persistence
      - ./config:/app/config  # Configuration files
    environment:
      - SLACK_BOT_TOKEN
      - ANYTHINGLLM_API_KEY
      - OPENAI_API_KEY
    restart: unless-stopped
```

**Development vs Production**:
- Development: Mount source code as volume for hot reload
- Production: Copy code into image for immutability

---

## 6. Configuration Management

### Decision: YAML Configuration + Environment Variables

**Rationale**:
- YAML for structured config (intervals, probabilities, persona parameters)
- Environment variables for secrets (API keys, tokens)
- `python-dotenv` for local development `.env` file support

**Configuration Structure** (`config/config.yml`):
```yaml
bot:
  persona:
    name: "Lukas the Bear"
    personality_file: "persona_prompts.yml"

  engagement:
    random_dm_interval_hours: 24
    thread_response_probability: 0.20
    active_hours:
      start: "08:00"
      end: "18:00"
      timezone: "America/New_York"

  image_posting:
    interval_days: 7
    channel: "#random"

  llm:
    provider: "${LLM_PROVIDER}"  # openai, anthropic, ollama, etc.
    model: "gpt-3.5-turbo"  # Provider-specific model name
    max_context_messages: 10
    max_tokens_per_request: 4000

  database:
    url: "sqlite:///data/lukas.db"
    conversation_retention_days: 90
```

---

## Summary of Decisions

| Question | Decision | Key Trade-off |
|----------|----------|---------------|
| Image Generation | DALL-E 3 (OpenAI) | Cost vs quality/simplicity - chose quality |
| Task Scheduling | APScheduler | Scale vs complexity - chose simplicity |
| LLM Context | Sliding window (10 pairs) | Memory vs cost - chose cost efficiency |
| Error Recovery | Exponential backoff + circuit breaker + degradation | Complexity vs reliability - chose reliability |
| Slack Integration | Socket Mode (Bolt SDK) | Scalability vs setup - chose simple setup |
| Configuration | YAML + env vars | Flexibility vs type safety - chose flexibility |

All decisions align with Constitution principles:
- **Documentation**: Each service will document its retry/fallback behavior
- **Smart Architecture**: Chose simplicity (APScheduler, SQLite, Socket Mode) over premature scaling
- **Pragmatic Testing**: Can mock external services easily with chosen patterns

---

## 7. MCP Integration for Enhanced Capabilities (Added: 2025-10-25)

### Decision: Official MCP Python SDK + LangChain/LangGraph + web-search-mcp

**Rationale**:
- **User Request**: Enhance Lukas's ability to answer questions requiring current information
- **Tool Access**: Web search enables answering "what is X?" questions beyond LLM training data
- **Autonomous Decision Making**: LangChain/LangGraph agent framework with create_react_agent allows Lukas to decide when tools are needed
- **Official SDK**: mcp>=1.0.0 provides native SSE client support, better maintained than third-party clients
- **No API Keys**: web-search-mcp uses browser automation (Playwright) against Bing/Brave/DuckDuckGo
- **Graceful Degradation**: Three-tier fallback (agent → LLM → emergency response) ensures system continues working if MCP servers unavailable
- **Persistent Connections**: SSE transport with background task lifecycle maintains persistent context (solves async cleanup issues)

**Alternatives Considered**:

| Approach | Pros | Cons | Why Rejected |
|----------|------|------|--------------|
| mcp-use (third-party) | Python-native, LangChain compatible | Less maintained than official SDK, missing SSE features | Official SDK provides better SSE support and maintenance |
| Direct API integration (Brave Search API) | Simple REST calls | Requires API key, costs money, less flexible | web-search-mcp is free and no signup required |
| Stdio MCP (npx per request) | Simpler deployment | 96% failure rate under load, 0.64 req/s throughput | Unacceptable performance for production |
| Custom web scraping | Full control | Maintenance burden, legal concerns, easily broken | web-search-mcp already solves this well |
| No enhancement | Simplest | Lukas can't answer current information questions | User explicitly requested enhanced capabilities |

**Architecture Decision**:

```
┌──────────────────────────────────────────┐
│  lukas-bot (Python)                      │
│  ┌────────────────────────────────────┐  │
│  │ Official MCP Python SDK (>=1.0.0)  │  │
│  │   - SSE client (sse_client)        │  │
│  │   - ClientSession management       │  │
│  │   - Background task lifecycle      │  │
│  │                                     │  │
│  │ LangChain/LangGraph Agent          │  │
│  │   - create_react_agent             │  │
│  │   - MCP → StructuredTool converter │  │
│  │   - Autonomous tool selection      │  │
│  │                                     │  │
│  │ Service Selection                  │  │
│  │   - get_llm_service()              │  │
│  │   - Three-tier fallback            │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │ HTTP/SSE (persistent)
               │ http://web-search-mcp:8080/sse
               │ (dev: :9765/sse)
┌──────────────▼───────────────────────────┐
│  web-search-mcp (Node.js)                │
│  ┌────────────────────────────────────┐  │
│  │ Supergateway (SSE bridge)          │  │
│  │      ↕ stdio                        │  │
│  │ web-search-mcp tools (3 tools):    │  │
│  │   - full-web-search                │  │
│  │   - get-web-search-summaries       │  │
│  │   - get-single-web-page-content    │  │
│  │ - Playwright browsers              │  │
│  │   (Chromium, Firefox)              │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Key Components**:

1. **Official MCP Python SDK (mcp>=1.0.0)**: Official Model Context Protocol client
   - Why chosen: Native SSE client support, officially maintained by Anthropic, best SSE integration
   - Key features: sse_client for persistent connections, ClientSession management, proper async context handling
   - Implementation: Background task lifecycle pattern maintains persistent SSE connection throughout bot lifetime
   - Solves: Async context cleanup issues with proper task ownership

2. **LangChain/LangGraph**: Agent framework for autonomous tool selection
   - Why chosen: Industry standard, well-documented, create_react_agent for tool-using agents
   - Enables Lukas to decide "do I need to search?" vs "I can answer this directly"
   - Tool conversion: MCP tools → LangChain StructuredTools with Pydantic schemas
   - Error handling: Wraps session.call_tool() with fallback responses

3. **web-search-mcp**: TypeScript MCP server for web search
   - Why chosen: No API keys, multi-engine fallback (Bing → Brave → DuckDuckGo)
   - 3 tools: full-web-search, get-web-search-summaries, get-single-web-page-content
   - Open source, MIT licensed
   - Implementation: src/services/llm_agent_service.py:485 lines

4. **Supergateway**: stdio ↔ SSE bridge
   - Why chosen: Enables persistent network connections to stdio-based MCP servers
   - Performance: 100x throughput improvement over spawning processes
   - Battle-tested, Docker-ready
   - Deployment: Runs in web-search-mcp container, exposes port 8080 (prod) / 9765 (dev)

**Implementation Notes**:

- **Backwards Compatibility**: Can disable MCP via `USE_MCP_AGENT=false` env var
- **Graceful Degradation**: Three-tier fallback (agent → LLM → emergency response)
- **Resource Limits**: web-search-mcp container limited to 2GB RAM (browser memory)
- **Health Checks**: Both containers have health monitoring
- **Docker Network**: Isolated `lukas-network` bridge for inter-container communication

**Implementation Learnings** (Added: 2025-10-26):

1. **Async Context Cleanup Solution**:
   - Problem: "exit cancel scope in different task" error when closing SSE connection
   - Root cause: SSE context created in one task, cleaned up in another
   - Solution: Background task lifecycle pattern keeps SSE context in same task throughout lifetime
   - Implementation: `_mcp_connection_lifecycle()` method maintains persistent connection until bot shutdown
   - Code location: src/services/llm_agent_service.py:_mcp_connection_lifecycle()

2. **Service Selection Pattern**:
   - `get_llm_service()` in message_handler.py selects appropriate service
   - Checks USE_MCP_AGENT env var and agent availability
   - Returns llm_agent_service if MCP available, otherwise standard llm_service
   - Enables seamless fallback without code changes

3. **Tool Conversion**:
   - MCP tool JSON schemas → Pydantic models via `create_model()`
   - Async wrapper functions for session.call_tool()
   - LangChain StructuredTool creation with proper typing
   - Error handling returns helpful fallback messages

4. **Testing Strategy**:
   - 8 unit tests: Fallback behavior, initialization, token estimation
   - 4 integration tests: MCP initialization, tool invocation, live connection, service selection
   - Mock MCP server for reliable unit tests
   - Live MCP test skipped unless MCP server running (pytest.skip)
   - 55% coverage of critical paths (following 80/20 rule)

5. **Deployment Configuration**:
   - Dev: docker-compose.dev.yml with port 9765
   - Prod: docker-compose.yml with port 8080
   - Separate Dockerfiles for bot and MCP server
   - Health checks ensure proper startup order

**Performance Characteristics**:

- Initial MCP connection: ~2-5s (during bot startup)
- Web search tool call: ~3-10s (depends on search engine response)
- Overall response time: Still <15s for tool-augmented responses (acceptable for Slack UX)
- Memory footprint: +500MB-2GB for MCP container (browsers + Node.js)

**Trade-offs**:

| Aspect | Gain | Cost |
|--------|------|------|
| Capabilities | Can answer current information questions | Increased system complexity |
| Performance | Persistent SSE = low latency | Additional container overhead |
| Reliability | Graceful degradation | More components that can fail |
| Cost | No API fees for search | Higher memory usage (~2GB) |

**Alignment with Constitution**:

- ✅ **Documentation**: MCP architecture documented in plan.md, README updated
- ✅ **Smart Architecture**: Chose battle-tested components (mcp-use, LangChain, Supergateway)
- ✅ **YAGNI**: Only added one MCP server (web search), not over-engineering with many tools
- ✅ **Pragmatic Testing**: Can mock MCP client in tests, graceful degradation testable

**Deployment Configuration**:

```yaml
# docker-compose.yml additions
services:
  web-search-mcp:
    build: docker/mcp-servers/web-search
    environment:
      - MAX_BROWSERS=3
      - BROWSER_TYPES=chromium,firefox
    deploy:
      resources:
        limits:
          memory: 2G
```

**User Impact**:

- ✅ Lukas can now answer "What's the latest version of Python?" type questions
- ✅ Maintains friendly bear personality even when using search
- ✅ No visible difference if MCP unavailable (seamless fallback)
- ✅ No additional API keys or accounts required

**Future Expansion**:

Easy to add more MCP servers later:
- Filesystem server (read documentation)
- GitHub server (check repository status)
- Jira server (create tickets)
- Weather API server (team location weather)

**Next Phase**: Proceed to data model design and API contract definitions.
