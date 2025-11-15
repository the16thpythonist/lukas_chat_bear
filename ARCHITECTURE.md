# Architecture Overview

This document describes the system architecture, design decisions, and component interactions for the Lukas the Bear chatbot project.

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Architectural Principles](#architectural-principles)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Design Patterns](#design-patterns)
- [Scalability Considerations](#scalability-considerations)
- [Security Architecture](#security-architecture)
- [Performance Optimization](#performance-optimization)
- [Future Enhancements](#future-enhancements)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Docker Network                            │
│                                                                     │
│  ┌──────────────────────┐       ┌──────────────────────────────┐  │
│  │   Bot Container      │       │   Dashboard Container        │  │
│  │  ┌────────────────┐  │       │  ┌────────────────────────┐ │  │
│  │  │   Slack Bot    │  │       │  │   Flask Backend       │ │  │
│  │  │  (Socket Mode) │  │       │  │   (REST API)          │ │  │
│  │  └────────────────┘  │       │  └────────────────────────┘ │  │
│  │  ┌────────────────┐  │       │  ┌────────────────────────┐ │  │
│  │  │  MCP Server    │◄─┼───────┼─►│   HTTP Client         │ │  │
│  │  │  (port 9766)   │  │       │  └────────────────────────┘ │  │
│  │  └────────────────┘  │       │  ┌────────────────────────┐ │  │
│  │  ┌────────────────┐  │       │  │   Vue.js Frontend     │ │  │
│  │  │ Internal API   │◄─┼───────┼──│   (SPA)               │ │  │
│  │  │  (port 5001)   │  │       │  └────────────────────────┘ │  │
│  │  └────────────────┘  │       └──────────────────────────────┘  │
│  │  ┌────────────────┐  │                                          │
│  │  │   SQLite DB    │  │       ┌──────────────────────────────┐  │
│  │  └────────────────┘  │       │   Web Search MCP             │  │
│  └──────────────────────┘       │   (Node.js + Playwright)     │  │
│           ▲                      └──────────────────────────────┘  │
│           │                                 ▲                       │
└───────────┼─────────────────────────────────┼───────────────────────┘
            │                                 │
            ▼                                 ▼
    ┌──────────────┐                 ┌──────────────┐
    │ Slack API    │                 │ Web Search   │
    │ (WebSocket)  │                 │ Engines      │
    └──────────────┘                 └──────────────┘
            ▲
            │
            ▼
    ┌──────────────┐
    │ OpenAI API   │
    │ (GPT + DALL-E)│
    └──────────────┘
```

### Key Components

1. **Bot Container** - Core chatbot application
   - Slack bot with Socket Mode connection
   - MCP server for tool exposure
   - Internal HTTP API for dashboard communication
   - SQLite database for persistence

2. **Dashboard Container** - Web admin interface
   - Flask REST API backend
   - Vue.js SPA frontend
   - Read-only database access
   - Session-based authentication

3. **Web Search MCP** - External search capabilities
   - Node.js server with Playwright
   - Browser automation for web scraping
   - SSE communication with bot

### Communication Patterns

| From | To | Protocol | Purpose |
|------|----|---------| --------|
| Bot | Slack API | WebSocket (Socket Mode) | Receive/send Slack events |
| Bot | OpenAI API | HTTPS REST | LLM completions, image generation |
| Bot | Web Search MCP | SSE (Server-Sent Events) | Search tool invocation |
| Bot | Slack Ops MCP | SSE | Internal tool invocation |
| Dashboard | Bot Internal API | HTTP REST | Trigger manual actions |
| Dashboard | Bot Database | SQLite (read-only) | Fetch analytics data |
| Frontend | Backend | HTTP REST + WebSocket | UI data & real-time updates |

---

## Architectural Principles

### 1. Separation of Concerns

**Principle**: Each component has a single, well-defined responsibility.

**Implementation**:
- **Bot**: Handles Slack communication and AI agent logic
- **Dashboard**: Provides monitoring and control interface
- **MCP Servers**: Expose specialized capabilities as tools

**Benefits**:
- Easier to test and maintain
- Clear boundaries for development
- Independent scaling of components

### 2. Microservices Architecture

**Principle**: System composed of small, independent services communicating over network.

**Implementation**:
- Bot, Dashboard, and MCP servers run in separate containers
- HTTP/SSE for inter-service communication
- Shared SQLite database (bot writes, dashboard reads)

**Benefits**:
- Independent deployment and scaling
- Technology diversity (Python, Node.js, Vue.js)
- Fault isolation (dashboard failure doesn't crash bot)

**Tradeoffs**:
- Increased operational complexity
- Network latency between services
- Data consistency challenges

### 3. Event-Driven Design

**Principle**: Components react to events rather than polling.

**Implementation**:
- Slack events trigger bot handlers
- APScheduler for time-based events
- SSE for MCP tool invocations

**Benefits**:
- Efficient resource usage
- Real-time responsiveness
- Loose coupling between components

### 4. Fail-Safe Defaults

**Principle**: System degrades gracefully when dependencies fail.

**Implementation**:
- Circuit breakers for external APIs
- Fallback responses when LLM fails
- Agent works without MCP tools if servers unavailable

**Benefits**:
- High availability
- User-friendly error handling
- Resilient to external service outages

---

## Component Architecture

### Bot Container

#### Layer Architecture

```
┌─────────────────────────────────────────────┐
│            Presentation Layer               │
│  (Slack Handlers: message, command, event)  │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│            Application Layer                │
│   (Services: LLM, Persona, Engagement)      │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│            Domain Layer                     │
│   (Models: Message, User, Conversation)     │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Data Access Layer                   │
│   (Repositories: TeamMember, Message)       │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Infrastructure Layer                │
│   (Database, External APIs, MCP Client)     │
└─────────────────────────────────────────────┘
```

#### Service Layer Responsibilities

**LLM Agent Service**:
- Manages LangChain agent with MCP tools
- Maintains MCP server connections (SSE)
- Provides conversation context to agent
- Handles tool selection and execution

**Persona Service**:
- Loads personality configuration from YAML
- Provides system prompts and greeting templates
- Maintains consistent bot character

**Engagement Service**:
- Tracks user interaction metrics
- Calculates engagement scores
- Determines random DM eligibility

**Image Service**:
- Generates DALL-E prompts
- Calls OpenAI API
- Posts images to Slack
- Stores metadata in database

**Scheduler Service**:
- Manages APScheduler instance
- Schedules random DMs and image posts
- Maintains task records in database

### Dashboard Container

#### Backend Architecture (Flask)

```
Flask Application Factory
    │
    ├── Blueprints
    │   ├── auth_bp      (login, logout, session check)
    │   ├── analytics_bp (overview, engagement)
    │   ├── controls_bp  (manual triggers)
    │   ├── tasks_bp     (task history)
    │   ├── images_bp    (image gallery)
    │   └── team_bp      (team member list)
    │
    ├── Services
    │   ├── database     (read-only DB access)
    │   ├── bot_invoker  (HTTP client for bot API)
    │   ├── analytics    (metric calculations)
    │   └── thumbnail    (image resizing)
    │
    ├── Middleware
    │   ├── auth         (session validation)
    │   ├── rate_limit   (request throttling)
    │   └── cors         (cross-origin handling)
    │
    └── Configuration
        ├── session      (Flask-Session)
        ├── logging      (structured logs)
        └── error_handlers (404, 500)
```

#### Frontend Architecture (Vue.js)

```
Vue 3 Application (Composition API)
    │
    ├── Router
    │   └── Routes: /, /controls, /images, /tasks, /login
    │
    ├── Views (Page Components)
    │   ├── Dashboard.vue      (analytics overview)
    │   ├── ManualControls.vue (trigger actions)
    │   ├── ImageGallery.vue   (generated images)
    │   ├── TaskHistory.vue    (audit log)
    │   └── Login.vue          (authentication)
    │
    ├── Components (Reusable)
    │   ├── StatCard.vue       (metric display)
    │   ├── ControlPanel.vue   (action UI)
    │   └── Navbar.vue         (navigation)
    │
    ├── Services (API Clients)
    │   ├── auth.js            (login, logout, check)
    │   ├── analytics.js       (fetch metrics)
    │   ├── controls.js        (trigger actions)
    │   └── ...
    │
    ├── Composables (Shared Logic)
    │   ├── useAuth.js         (authentication state)
    │   └── useApi.js          (HTTP request wrapper)
    │
    └── Utils
        └── date.js            (date formatting)
```

### MCP Architecture

#### Model Context Protocol (MCP)

**Purpose**: Standardized protocol for exposing tools to LLM agents.

**Architecture**:

```
┌─────────────────────────────────────────────────────┐
│                   LLM Agent                         │
│  (Decides which tools to use based on user intent)  │
└─────────────────────────────────────────────────────┘
                    │
                    │ Function calling
                    ▼
┌─────────────────────────────────────────────────────┐
│                MCP Client                           │
│  (Manages connections to multiple MCP servers)      │
└─────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ Slack Ops MCP    │    │ Web Search MCP   │
│ (5 tools)        │    │ (3 tools)        │
│ - post_message   │    │ - full_search    │
│ - create_reminder│    │ - summaries      │
│ - get_team_info  │    │ - get_page       │
│ - update_config  │    └──────────────────┘
│ - generate_image │
└──────────────────┘
```

**Benefits**:
- Decoupled tool providers
- Easy to add new capabilities
- Standard protocol for LLM integration
- Tools testable independently

**Communication**: Server-Sent Events (SSE) over HTTP
- Long-lived connections
- Server can push updates to client
- Efficient for real-time tool invocation

---

## Data Flow

### User Message Processing

```
1. User sends message in Slack
   │
   ▼
2. Slack sends event via WebSocket (Socket Mode)
   │
   ▼
3. Bot receives event in message_handler.py
   │
   ▼
4. Handler validates event and extracts data
   │
   ▼
5. Message saved to database (messages table)
   │
   ▼
6. MessageContextService fetches conversation history
   │
   ▼
7. LLMAgentService.generate_response() called
   │
   ├──▶ Builds conversation context
   │
   ├──▶ Determines if tools needed
   │
   ├──▶ Calls LangChain agent with MCP tools
   │    │
   │    ├──▶ Agent analyzes user intent
   │    │
   │    ├──▶ Decides to call tool (e.g., web search)
   │    │
   │    ├──▶ MCP client invokes tool via SSE
   │    │
   │    └──▶ Tool result returned to agent
   │
   ├──▶ Agent generates final response
   │
   └──▶ Response text returned
   │
   ▼
8. Response saved to database
   │
   ▼
9. Response sent to Slack via API
   │
   ▼
10. User sees response in Slack
```

### Manual Image Generation Flow

```
1. User clicks "Generate Image" in dashboard
   │
   ▼
2. Frontend calls POST /api/controls/generate-image
   │
   ▼
3. Dashboard backend validates session and rate limit
   │
   ▼
4. Backend calls bot internal API via HTTP
   POST http://lukas-bear-bot-dev:5001/api/internal/generate-image
   │
   ▼
5. Bot internal API receives request
   │
   ▼
6. ImageService.generate_and_post() called
   │
   ├──▶ Generate DALL-E prompt (optional theme)
   │
   ├──▶ Call OpenAI API (DALL-E)
   │
   ├──▶ Download generated image
   │
   ├──▶ Upload to Slack channel
   │
   ├──▶ Save metadata to database (generated_images)
   │
   └──▶ Create audit log (scheduled_tasks)
   │
   ▼
7. Bot API returns success with image metadata
   │
   ▼
8. Dashboard backend returns response to frontend
   │
   ▼
9. Frontend displays success message
```

### Scheduled Task Execution

```
1. APScheduler triggers job (e.g., random_dm_task)
   │
   ▼
2. scheduler_service.py: execute_random_dm()
   │
   ▼
3. Create scheduled_task record (status: pending)
   │
   ▼
4. Update status to "running"
   │
   ▼
5. ProactiveDMService.send_random_dm()
   │
   ├──▶ Query eligible users (last DM > X hours ago)
   │
   ├──▶ Calculate engagement weights
   │
   ├──▶ Randomly select user
   │
   ├──▶ Generate greeting via PersonaService
   │
   ├──▶ Open DM conversation (Slack API)
   │
   ├──▶ Send message (Slack API)
   │
   └──▶ Update user.last_proactive_dm_at
   │
   ▼
6. Update scheduled_task status to "completed"
   │
   ▼
7. Schedule next execution
```

---

## Technology Stack

### Backend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Runtime | Python | 3.11+ | Core application language |
| Bot Framework | Slack Bolt | 1.18+ | Slack integration (Socket Mode) |
| LLM Framework | LangChain | 0.3+ | Agent orchestration |
| Agent Framework | LangGraph | 0.2+ | ReAct agent pattern |
| LLM API | OpenAI | 1.3+ | GPT completions, DALL-E |
| MCP SDK | mcp | 1.0+ | Tool protocol client/server |
| Web Framework | Flask | 3.0+ | Dashboard REST API |
| ORM | SQLAlchemy | 2.0+ | Database abstraction |
| Migrations | Alembic | 1.12+ | Schema versioning |
| Scheduler | APScheduler | 3.10+ | Background tasks |
| HTTP Client | httpx | 0.27+ | Async HTTP requests |
| Retry Logic | tenacity | 8.2+ | Fault tolerance |
| Circuit Breaker | pybreaker | 1.0+ | Service protection |

### Frontend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Vue.js | 3.x | Reactive UI framework |
| Build Tool | Vite | 4.x | Fast dev server & bundler |
| Router | Vue Router | 4.x | SPA navigation |
| HTTP Client | Axios | 1.x | API communication |
| UI Components | Custom | - | Tailwind CSS + custom |

### Infrastructure

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Containerization | Docker | 20.10+ | Application packaging |
| Orchestration | Docker Compose | 2.0+ | Multi-container management |
| Database | SQLite | 3.x | Data persistence |
| Session Storage | Flask-Session | - | User sessions (filesystem/Redis) |
| MCP Server (Web Search) | Node.js + Playwright | 18+ | Browser automation |

### External Services

| Service | Purpose | Criticality |
|---------|---------|-------------|
| Slack API | Bot communication | Critical |
| OpenAI API | LLM completions & image generation | Critical |
| Web Search Engines | MCP web search tool | Non-critical |

---

## Design Patterns

### 1. Repository Pattern

**Purpose**: Abstract data access logic from business logic.

**Implementation**:
```python
# src/repositories/team_member_repo.py
class TeamMemberRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    def get_by_slack_id(self, slack_id: str) -> Optional[TeamMember]:
        return self.db_session.query(TeamMember)\
            .filter(TeamMember.slack_user_id == slack_id).first()

    def get_all_active(self) -> List[TeamMember]:
        return self.db_session.query(TeamMember)\
            .filter(TeamMember.total_messages_sent > 0).all()
```

**Benefits**:
- Testable (easy to mock)
- Centralized data access
- Database agnostic (can swap SQLite for PostgreSQL)

### 2. Service Layer Pattern

**Purpose**: Encapsulate business logic in reusable services.

**Implementation**:
```python
# src/services/engagement_service.py
class EngagementService:
    def __init__(self, db_session):
        self.repo = TeamMemberRepository(db_session)

    def calculate_engagement_score(self, user_id: str) -> float:
        user = self.repo.get_by_slack_id(user_id)
        # Complex business logic
        return score

    def get_eligible_dm_users(self) -> List[TeamMember]:
        # Business logic for DM eligibility
        return eligible_users
```

**Benefits**:
- Reusable across handlers
- Testable in isolation
- Clear separation of concerns

### 3. Factory Pattern

**Purpose**: Create complex objects with configuration.

**Implementation**:
```python
# dashboard/backend/app.py
def create_app(config=None):
    """Application factory for Flask."""
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config or DefaultConfig)

    # Initialize extensions
    Session(app)
    CORS(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    return app
```

**Benefits**:
- Multiple configurations (dev, test, prod)
- Easier testing (inject test config)
- Delayed initialization

### 4. Circuit Breaker Pattern

**Purpose**: Prevent cascading failures when external services fail.

**Implementation**:
```python
from pybreaker import CircuitBreaker

openai_breaker = CircuitBreaker(
    fail_max=5,          # Open after 5 failures
    reset_timeout=60     # Retry after 60 seconds
)

@openai_breaker
async def call_openai(prompt: str) -> str:
    response = await openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

**States**:
- **Closed**: Normal operation
- **Open**: Failures exceeded, reject immediately
- **Half-Open**: Test if service recovered

**Benefits**:
- Fast failure (don't wait for timeout)
- Automatic recovery
- Reduced load on failing service

### 5. Decorator Pattern

**Purpose**: Add behavior to functions without modifying them.

**Implementation**:
```python
# dashboard/backend/auth.py
def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_authenticated' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/analytics/overview')
@require_auth
def get_overview():
    # Implementation
```

**Benefits**:
- DRY (Don't Repeat Yourself)
- Composable (stack multiple decorators)
- Clear separation of concerns

### 6. Observer Pattern (Event-Driven)

**Purpose**: React to events without tight coupling.

**Implementation**:
```python
# Slack Bolt framework uses this internally
@app.message("hello")
async def handle_hello(message, say):
    await say(f"Hi there, <@{message['user']}>!")

# Multiple handlers can observe same event
@app.message("hello")
async def log_hello(message):
    logger.info(f"User {message['user']} said hello")
```

**Benefits**:
- Loose coupling
- Easy to add new behaviors
- Event-driven architecture

---

## Scalability Considerations

### Current Limitations

1. **SQLite Database**
   - Single-writer constraint
   - File-based (no network access)
   - Limited concurrent connections

2. **Monolithic Bot Container**
   - All bot logic in single container
   - Vertical scaling only

3. **Stateful Sessions**
   - Dashboard sessions in filesystem
   - Can't load balance across instances

### Scaling Strategies

#### Horizontal Scaling (Multiple Bot Instances)

**Challenge**: Slack Socket Mode doesn't support multiple connections per app.

**Solutions**:
1. **Switch to HTTP Events** instead of Socket Mode
   - Allows load balancer in front of multiple bot instances
   - Requires public endpoint with SSL

2. **Partition Workload**
   - Run multiple Slack apps (different workspaces)
   - Each app has dedicated bot instance

#### Database Scaling

**Migration Path**: SQLite → PostgreSQL

**Benefits**:
- Multiple writers (concurrent access)
- Network access (separate server)
- Better performance at scale
- Replication support

**Changes Needed**:
- Update SQLAlchemy connection string
- Adjust migrations for PostgreSQL syntax
- Configure connection pooling

#### Caching Layer

**Add Redis** for frequently accessed data:

```python
import redis

cache = redis.Redis(host='redis', port=6379)

def get_user_engagement(user_id: str) -> float:
    # Try cache first
    cached = cache.get(f'engagement:{user_id}')
    if cached:
        return float(cached)

    # Calculate and cache
    score = calculate_engagement_score(user_id)
    cache.setex(f'engagement:{user_id}', 3600, score)
    return score
```

**Use Cases**:
- User engagement scores
- Analytics aggregations
- Session storage (dashboard)
- Rate limiting counters

#### Message Queue

**Add Celery** for background task processing:

```python
from celery import Celery

celery = Celery('lukas', broker='redis://redis:6379')

@celery.task
def process_message_async(message_data):
    # Process message in background
    llm_service.generate_response(...)

# In handler
@app.message()
async def handle_message(message):
    process_message_async.delay(message)
    # Return immediately
```

**Benefits**:
- Non-blocking handlers
- Retry failed tasks
- Distribute work across workers

---

## Security Architecture

### Authentication & Authorization

**Dashboard**:
- Session-based authentication
- Secure cookies (HttpOnly, Secure, SameSite)
- Password hashing (future: bcrypt)
- CSRF protection (future)

**Bot Internal API**:
- No authentication (trusted internal network)
- Not exposed to public internet
- Docker network isolation

**Slack Integration**:
- Socket Mode (no public endpoint needed)
- Signature verification (if using HTTP events)
- OAuth tokens with minimal scopes

### Data Protection

**Secrets Management**:
```bash
# .env file (not committed)
SLACK_BOT_TOKEN=xoxb-...
OPENAI_API_KEY=sk-...
DASHBOARD_SECRET_KEY=random-32-chars
```

**Environment Variable Injection**:
- Docker Compose passes env vars to containers
- No secrets in source code or Dockerfiles

**Future: Secrets Manager**:
- Use HashiCorp Vault or AWS Secrets Manager
- Rotate secrets automatically
- Audit secret access

### Network Security

**Container Isolation**:
- Bot container only exposes MCP port internally
- Dashboard container exposes port 8080 externally
- Web Search MCP fully internal

**Future: Reverse Proxy**:
```
Internet → Nginx (SSL termination) → Dashboard Container
            ├── Rate limiting
            ├── DDoS protection
            └── Request logging
```

### Input Validation

**User Messages**:
- Slack API handles message sanitization
- Bot doesn't execute arbitrary code

**Dashboard API**:
```python
from flask import request
from werkzeug.exceptions import BadRequest

@app.route('/api/controls/generate-image', methods=['POST'])
def generate_image():
    data = request.get_json()

    # Validate theme
    theme = data.get('theme', '')
    if len(theme) > 200:
        raise BadRequest("Theme too long")

    # Validate channel ID format
    channel_id = data.get('channel_id', '')
    if channel_id and not channel_id.startswith('C'):
        raise BadRequest("Invalid channel ID")
```

### Audit Logging

**Actions Logged**:
- All manual triggers (dashboard)
- Scheduled task execution
- Authentication events
- API errors

**Log Storage**:
```python
logger.info(
    f"Manual DM triggered",
    extra={
        'action': 'manual_dm',
        'user': session_id,
        'target': target_user,
        'timestamp': datetime.utcnow()
    }
)
```

**Future: Centralized Logging**:
- Ship logs to ELK stack or Splunk
- Alerting on suspicious patterns
- Long-term retention

---

## Performance Optimization

### Current Optimizations

1. **Async I/O**
   - All LLM calls async (no blocking)
   - Slack API calls async
   - MCP tool invocations async

2. **Connection Pooling**
   - SQLAlchemy connection pool
   - httpx connection reuse
   - Slack client connection management

3. **Lazy Loading**
   - MCP servers initialized on demand
   - Dashboard services initialized per-request

4. **Caching**
   - Dashboard thumbnails cached on disk
   - Persona templates cached in memory

### Performance Metrics

**Response Times** (development):
- Simple message: ~1-2 seconds
- Message with tool use: ~3-5 seconds
- Manual image generation: ~10-20 seconds
- Dashboard page load: ~200-500ms

**Resource Usage**:
- Bot container: ~200-400MB RAM
- Dashboard container: ~150-250MB RAM
- Web Search MCP: ~300-500MB RAM

### Bottlenecks & Solutions

**Bottleneck 1: OpenAI API Latency**
- **Problem**: GPT responses take 1-3 seconds
- **Solution**: Use streaming responses (future)
- **Solution**: Cache common responses

**Bottleneck 2: Database Lock Contention**
- **Problem**: SQLite single-writer limitation
- **Solution**: Migrate to PostgreSQL
- **Solution**: Batch writes where possible

**Bottleneck 3: Image Generation**
- **Problem**: DALL-E takes 10-20 seconds
- **Solution**: Queue image generation (Celery)
- **Solution**: Show progress indicator to user

---

## Future Enhancements

### Short-Term (1-3 months)

1. **Advanced Analytics**
   - Conversation sentiment analysis
   - Topic modeling
   - User activity heatmaps

2. **Improved Scheduling**
   - Per-user DM preferences
   - Timezone-aware scheduling
   - Smart scheduling (avoid meetings)

3. **Enhanced Personality**
   - Multiple personas (formal, casual, technical)
   - Context-aware tone adjustment
   - Emoji usage based on conversation

### Medium-Term (3-6 months)

1. **Multi-Workspace Support**
   - Deploy to multiple Slack workspaces
   - Centralized management dashboard
   - Per-workspace configuration

2. **Plugin System**
   - Custom MCP servers for organization-specific tools
   - Plugin marketplace
   - Hot-reload plugins without restart

3. **Advanced Integrations**
   - Google Calendar (check availability)
   - Jira (create/update tickets)
   - GitHub (code search, PR status)

### Long-Term (6-12 months)

1. **Multi-LLM Support**
   - Anthropic Claude
   - Google Gemini
   - Self-hosted models (Ollama)

2. **Voice Interaction**
   - Slack huddle integration
   - Speech-to-text / text-to-speech
   - Natural conversation flow

3. **Advanced Learning**
   - Fine-tuning on organization data
   - RAG (Retrieval-Augmented Generation)
   - Long-term memory system

---

## Architecture Decision Records (ADRs)

### ADR-001: Why Microservices?

**Decision**: Split bot and dashboard into separate containers.

**Rationale**:
- Dashboard doesn't need OpenAI SDK (100+ MB)
- Independent scaling
- Fault isolation

**Consequences**:
- Increased complexity
- Network latency between services
- Need for internal API

### ADR-002: Why SQLite?

**Decision**: Use SQLite for initial implementation.

**Rationale**:
- Simple setup (no separate DB server)
- Sufficient for single-workspace deployment
- Easy backup (single file)

**Consequences**:
- Limited concurrency
- Not suitable for multi-instance deployment
- Migration path to PostgreSQL exists

### ADR-003: Why Socket Mode?

**Decision**: Use Slack Socket Mode instead of HTTP Events API.

**Rationale**:
- No public endpoint required
- Simpler deployment (no SSL/domain needed)
- Lower latency (persistent WebSocket)

**Consequences**:
- Can't horizontally scale bot
- Requires Slack App-Level Token
- Enterprise Grid limitations

### ADR-004: Why MCP for Tools?

**Decision**: Use Model Context Protocol instead of custom tool system.

**Rationale**:
- Standard protocol (interoperable)
- Easy to add new tools
- Community MCP servers available

**Consequences**:
- Dependency on MCP SDK
- SSE connection management complexity
- Learning curve for new protocol

---

**Last Updated**: 2025-10-29
**Architecture Version**: 1.0
