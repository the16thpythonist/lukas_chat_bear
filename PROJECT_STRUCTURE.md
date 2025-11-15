# Project Structure

This document provides an overview of the Lukas the Bear chatbot project organization, explaining the purpose of each major directory and key files.

## 📋 Table of Contents

- [High-Level Overview](#high-level-overview)
- [Top-Level Directories](#top-level-directories)
- [Bot Source Code (`src/`)](#bot-source-code-src)
- [Dashboard (`dashboard/`)](#dashboard-dashboard)
- [Docker Infrastructure (`docker/`)](#docker-infrastructure-docker)
- [Configuration (`config/`)](#configuration-config)
- [Database Migrations (`migrations/`)](#database-migrations-migrations)
- [Testing (`tests/`)](#testing-tests)
- [Key Files](#key-files)

---

## High-Level Overview

```text
lukas_chat_bear/
├── src/                    # Bot application source code
├── dashboard/              # Web dashboard (admin UI)
├── docker/                 # Docker configuration and MCP servers
├── config/                 # YAML configuration files
├── migrations/             # Database schema migrations (Alembic)
├── tests/                  # Bot test suite
├── scripts/                # Utility scripts
├── specs/                  # Feature specifications and planning docs
├── data/                   # Runtime data (SQLite database, logs)
└── [config files]          # pyproject.toml, docker-compose.yml, etc.
```

**Architecture**: Microservices-based with three main containers:
1. **Bot Container** - Slack bot with MCP server and Internal API
2. **Dashboard Container** - Web UI with Flask backend + Vue.js frontend
3. **Web Search MCP** - External MCP server for web search capabilities

---

## Top-Level Directories

### `src/` - Bot Application

The core Slack bot application written in Python.

**Purpose**: Implements the chatbot personality, Slack integration, AI agent capabilities, and background tasks.

**Key Components**:
- Main bot entry point (`bot.py`)
- MCP server for Slack operations (`mcp_server.py`)
- Internal API for dashboard communication (`api/internal_api.py`)
- Event handlers, services, models, and utilities

See [Bot Source Code](#bot-source-code-src) for detailed breakdown.

### `dashboard/` - Web Admin Interface

A web-based dashboard for monitoring and controlling the bot.

**Purpose**: Provides a user-friendly interface for viewing analytics, manual controls, and bot status.

**Key Components**:
- Flask backend API (`backend/`)
- Vue.js 3 frontend SPA (`frontend/`)
- Session management and authentication

See [Dashboard](#dashboard-dashboard) for detailed breakdown.

### `docker/` - Containerization

Docker configuration for multi-container deployment.

**Purpose**: Containerize services and manage inter-service networking.

**Contents**:
- `Dockerfile` - Bot container image definition
- `start-bot.sh` - Multi-process startup script (MCP + Internal API + Bot)
- `mcp-servers/` - External MCP server containers (web-search)

See [Docker Infrastructure](#docker-infrastructure-docker) for details.

### `config/` - Configuration Files

YAML configuration files for bot behavior and personality.

**Purpose**: Centralize all configurable bot settings without code changes.

**Key Files**:
- `config.yml` - Bot settings (DM intervals, channels, feature flags)
- `persona_prompts.yml` - Lukas the Bear personality definitions
- `circuit_breaker.yml` - Fault tolerance configuration

### `migrations/` - Database Schema

Alembic database migration scripts.

**Purpose**: Version control for database schema changes.

**Structure**:
```text
migrations/
├── versions/               # Individual migration scripts
├── env.py                 # Alembic environment configuration
└── script.py.mako         # Migration template
```

**Usage**: `alembic upgrade head` to apply migrations

### `tests/` - Test Suite

Comprehensive test coverage for bot functionality.

**Purpose**: Ensure code quality and prevent regressions.

**Structure**:
```text
tests/
├── unit/                  # Unit tests (isolated component testing)
│   └── services/         # Service layer tests
├── integration/          # Integration tests (multi-component)
│   ├── handlers/        # Handler integration tests
│   └── services/        # Service integration tests
├── fixtures/            # Test data and mocks
└── helpers/             # Test utilities
```

**Run Tests**: `pytest` (from project root)

### `scripts/` - Utility Scripts

Helper scripts for development and maintenance tasks.

**Purpose**: Automate common operations.

**Examples**:
- Database seeding scripts
- Migration utilities
- Development helpers

### `specs/` - Feature Specifications

Feature planning documents and implementation guides.

**Purpose**: Document feature requirements, designs, and checklists.

**Structure**:
```text
specs/
├── 001-lukas-bear-chatbot/    # Core bot feature spec
│   ├── spec.md                # Feature specification
│   ├── plan.md                # Implementation plan
│   ├── tasks.md               # Task breakdown
│   └── checklists/            # Requirement checklists
└── 002-web-dashboard/         # Dashboard feature spec
    └── [same structure]
```

**Created by**: `/speckit.*` slash commands

### `data/` - Runtime Data

Persistent data directory (gitignored).

**Purpose**: Store database and runtime artifacts.

**Contents**:
- `lukas.db` - SQLite database (conversations, team members, tasks, images)
- Logs (if file logging is enabled)
- Cached data

**⚠️ Important**: Never commit this directory - contains sensitive data

---

## Bot Source Code (`src/`)

Detailed breakdown of the bot application structure.

### Directory Structure

```text
src/
├── bot.py                      # Main application entry point
├── mcp_server.py              # Slack Operations MCP server (port 9766)
│
├── api/                       # Internal HTTP APIs
│   └── internal_api.py       # Dashboard integration API (port 5001)
│
├── handlers/                  # Slack event handlers
│   ├── message_handler.py    # DM and mention handling
│   ├── thread_handler.py     # Thread reply handling
│   ├── command_handler.py    # Command processing
│   └── event_handler.py      # Workspace events (member_joined, etc.)
│
├── services/                  # Business logic layer
│   ├── llm_service.py        # Standard LLM service (no tools)
│   ├── llm_agent_service.py  # MCP-enabled agent with tools
│   ├── persona_service.py    # Personality management
│   ├── command_service.py    # Command execution logic
│   ├── engagement_service.py # User engagement tracking
│   ├── image_service.py      # DALL-E image generation
│   ├── proactive_dm_service.py # Random DM sending
│   ├── scheduler_service.py  # APScheduler background tasks
│   └── message_context_service.py # Conversation context
│
├── models/                    # SQLAlchemy ORM models
│   ├── message.py            # Chat messages
│   ├── team_member.py        # Slack users
│   ├── conversation.py       # Conversation threads
│   ├── scheduled_task.py     # Task audit log
│   ├── generated_image.py    # DALL-E images
│   └── bot_config.py         # Configuration storage
│
├── repositories/              # Data access layer
│   ├── team_member_repo.py   # Team member CRUD
│   ├── message_repo.py       # Message CRUD
│   ├── conversation_repo.py  # Conversation CRUD
│   └── image_repo.py         # Image CRUD
│
└── utils/                     # Shared utilities
    ├── logger.py             # Logging configuration
    ├── database.py           # Database session management
    ├── config_loader.py      # YAML config loading
    ├── retry.py              # Retry decorators
    └── token_counter.py      # Token estimation
```

### Key Files

#### `bot.py`
**Purpose**: Main application entry point. Initializes Slack Bolt app, registers handlers, starts scheduler, and runs Socket Mode connection.

**Key Responsibilities**:
- Initialize Slack app (Socket Mode)
- Set up database connection
- Initialize services (LLM, scheduler, image generation)
- Register event handlers
- Start background tasks
- Run the bot

#### `mcp_server.py`
**Purpose**: Model Context Protocol server exposing Slack operations as tools for the LLM agent.

**Exposed Tools** (5 total):
- `post_message_to_channel` - Send messages to channels
- `create_reminder` - Schedule reminders for users
- `get_team_info` - Retrieve workspace/bot information
- `update_bot_config` - Change bot settings (admin only)
- `generate_and_post_image` - Create DALL-E images (admin only)

**Port**: 9766 (internal Docker network)

#### `api/internal_api.py`
**Purpose**: Flask API for dashboard to trigger bot actions via HTTP.

**Endpoints**:
- `GET /api/internal/health` - Health check
- `POST /api/internal/generate-image` - Trigger DALL-E generation
- `POST /api/internal/send-dm` - Send proactive DM (random or targeted)

**Port**: 5001 (internal Docker network, not exposed to host)

**Architecture Note**: This allows dashboard to invoke bot services without importing bot dependencies.

---

## Dashboard (`dashboard/`)

Web-based admin interface for bot management and analytics.

### Directory Structure

```text
dashboard/
├── Dockerfile.dev              # Development container configuration
├── start-dev.sh               # Dev startup script (backend + frontend HMR)
│
├── backend/                   # Flask REST API
│   ├── app.py                # Flask app factory
│   ├── auth.py               # Session-based authentication
│   │
│   ├── routes/               # API endpoints
│   │   ├── auth.py          # Login/logout
│   │   ├── analytics.py     # Bot analytics data
│   │   ├── controls.py      # Manual trigger actions
│   │   ├── tasks.py         # Scheduled task history
│   │   ├── images.py        # Generated images gallery
│   │   └── team.py          # Team member list
│   │
│   ├── services/             # Business logic
│   │   ├── database.py      # Read-only DB access
│   │   ├── bot_invoker.py   # HTTP client for bot API
│   │   ├── analytics.py     # Analytics calculations
│   │   └── thumbnail.py     # Image thumbnail generation
│   │
│   └── utils/                # Helpers
│       └── rate_limit.py    # Rate limiting decorator
│
└── frontend/                 # Vue.js 3 SPA
    ├── vite.config.js       # Vite build configuration
    ├── index.html           # HTML entry point
    │
    └── src/
        ├── main.js          # Vue app initialization
        ├── App.vue          # Root component
        │
        ├── router/          # Vue Router configuration
        │   └── index.js    # Route definitions
        │
        ├── views/           # Page components
        │   ├── Dashboard.vue      # Main overview
        │   ├── ManualControls.vue # Trigger actions
        │   ├── ImageGallery.vue   # Image history
        │   ├── TaskHistory.vue    # Task audit log
        │   └── Login.vue          # Login page
        │
        ├── components/      # Reusable UI components
        │   ├── StatCard.vue       # Metric display
        │   ├── ControlPanel.vue   # Action trigger UI
        │   └── Navbar.vue         # Navigation bar
        │
        ├── services/        # API clients
        │   ├── auth.js            # Authentication API
        │   ├── analytics.js       # Analytics API
        │   ├── controls.js        # Manual controls API
        │   ├── tasks.js           # Task history API
        │   ├── images.js          # Image gallery API
        │   └── team.js            # Team members API
        │
        ├── composables/     # Vue composables (shared logic)
        │   ├── useAuth.js         # Authentication state
        │   └── useApi.js          # API request wrapper
        │
        └── utils/           # Helpers
            └── date.js            # Date formatting utilities
```

### Architecture Notes

**Backend**: Flask REST API serving JSON data
- **Database Access**: Read-only queries to bot's SQLite database
- **Bot Communication**: HTTP requests to bot's internal API (port 5001)
- **Authentication**: Session-based with secure cookies

**Frontend**: Vue.js 3 with Composition API
- **State Management**: Reactive refs and composables (no Vuex/Pinia)
- **Routing**: Vue Router for SPA navigation
- **Build Tool**: Vite for fast development and optimized builds
- **API Communication**: Axios for HTTP requests

**Development Mode**:
- Backend: Flask debug mode with auto-reload
- Frontend: Vite dev server with Hot Module Replacement (HMR)
- Ports: Backend (8080), Frontend (5173)

**Production Mode**:
- Backend serves static frontend build at `backend/dist/`
- Single port (8080) for entire dashboard

---

## Docker Infrastructure (`docker/`)

Containerization configuration and orchestration.

### Files

#### `Dockerfile`
**Purpose**: Build bot container image (Python 3.11-slim).

**Key Steps**:
1. Install system dependencies
2. Copy requirements and install Python packages
3. Copy source code
4. Set up startup script
5. Expose MCP port (9766)

**Entrypoint**: `docker/start-bot.sh`

#### `start-bot.sh`
**Purpose**: Multi-process startup script for bot container.

**Process Management** (runs 3 processes):
1. **MCP Server** (background) - Slack operations tools on port 9766
2. **Internal API** (background) - Dashboard integration on port 5001
3. **Slack Bot** (foreground) - Main bot application (Socket Mode)

**Lifecycle**:
- Runs database migrations (`alembic upgrade head`)
- Starts MCP server and waits for readiness
- Starts Internal API and waits for readiness
- Starts bot in foreground
- Cleanup on exit (kills background processes)

#### `mcp-servers/web-search/`
**Purpose**: External MCP server container for web search capabilities.

**Technology**: Node.js + Playwright (browser automation)

**Capabilities**:
- Full web search with content extraction
- Lightweight search summaries
- Single page content fetching

**Port**: 9765 (internal Docker network)

### Docker Compose Files

#### `docker-compose.yml` (Production)
**Purpose**: Production deployment configuration.

**Services**:
- `lukas-bot` - Main bot container
- `web-search-mcp` - Web search MCP server

**Features**:
- Health checks for all services
- Resource limits
- Automatic restart policies
- Named volumes for persistence

#### `docker-compose.dev.yml` (Development)
**Purpose**: Development environment with live code reloading.

**Additional Services**:
- `dashboard-dev` - Dashboard with HMR support

**Features**:
- Source code mounted as volumes (hot reload)
- Debug logging enabled
- Exposed ports for direct access
- Named volumes for sessions/thumbnails

**Usage**: `docker-compose -f docker-compose.dev.yml up`

### Networking

**Internal Docker Network** (`lukas-network-dev`):
- Bot container: `lukas-bear-bot-dev`
- Dashboard container: `dashboard-dev`
- Web Search MCP: `web-search-mcp-dev`

**Service Communication**:
- Dashboard → Bot API: `http://lukas-bear-bot-dev:5001`
- Bot → Web Search MCP: `http://web-search-mcp-dev:9765/sse`
- Bot → Slack Operations MCP: `http://localhost:9766/sse` (same container)

**Exposed Ports** (development):
- `8080` - Dashboard web UI
- `5173` - Vite dev server (frontend HMR)
- `9766` - Slack Operations MCP (for debugging)
- `9765` - Web Search MCP (for debugging)

---

## Configuration (`config/`)

YAML-based configuration for bot behavior.

### `config.yml`

**Purpose**: Main bot configuration file.

**Sections**:

```yaml
bot:
  name: "Lukas the Bear"
  timezone: "America/New_York"

  proactive_dm:
    enabled: true
    interval_hours: 12
    quiet_hours_start: 22
    quiet_hours_end: 8

  image_posting:
    enabled: true
    interval_days: 7
    channel: "#random"

  thread_participation:
    probability: 0.3
    min_messages: 3

  llm:
    model: "gpt-5-mini-2025-08-07"
    max_tokens: 8000
    temperature: 0.7

  features:
    use_mcp_agent: true
    enable_web_search: true
```

**Key Settings**:
- **Proactive DM**: When and how often to send random DMs
- **Image Posting**: DALL-E image generation schedule
- **Thread Participation**: Probability of joining conversations
- **LLM**: Model selection and parameters
- **Features**: Feature flags for MCP integration

### `persona_prompts.yml`

**Purpose**: Define Lukas the Bear's personality and behavior.

**Sections**:

```yaml
persona:
  name: "Lukas the Bear"
  description: "A friendly, helpful bear who loves technology and helping the team"

  system_prompt: |
    You are Lukas the Bear, a friendly and knowledgeable AI assistant...
    [Full personality definition]

  greeting_templates:
    - "Hey there! 🐻"
    - "Howdy! What can I help you with?"
    - "Hello! Lukas here, ready to assist!"

  fallback_responses:
    - "Hmm, I'm not sure about that. Can you rephrase?"
    - "That's a tough one! Let me think..."

  tone:
    - friendly
    - professional
    - enthusiastic
    - helpful
```

**Personality Traits**:
- Friendly and approachable
- Professional but not stiff
- Knowledgeable about technology
- Team-oriented

### `circuit_breaker.yml`

**Purpose**: Configure fault tolerance for external services.

**Settings**:

```yaml
circuit_breaker:
  openai_api:
    fail_max: 5               # Failures before opening circuit
    reset_timeout: 60         # Seconds before retry
    expected_exception: APIError

  slack_api:
    fail_max: 3
    reset_timeout: 30

  mcp_servers:
    fail_max: 5
    reset_timeout: 60
```

**How It Works**:
- Tracks consecutive failures to external services
- "Opens circuit" after threshold (stops calling service)
- Automatically retries after timeout period
- Prevents cascading failures

---

## Database Migrations (`migrations/`)

Alembic migration system for database schema versioning.

### Structure

```text
migrations/
├── versions/                           # Migration scripts
│   ├── 20251026_initial_schema.py     # Initial tables
│   ├── 20251027_add_mcp_fields.py     # MCP-related columns
│   └── 20251028_remove_unique_constraint.py
├── env.py                             # Alembic environment config
├── script.py.mako                     # New migration template
└── alembic.ini                        # Alembic configuration
```

### Common Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history
```

### Migration Naming Convention

Format: `YYYYMMDD_HHMM_<hash>_<description>.py`

Example: `20251028_2127_d6afc466f142_remove_job_id_unique_constraint_add_job_.py`

### Database Schema

**Tables**:
- `team_members` - Slack workspace users
- `conversations` - DM and thread conversations
- `messages` - Individual chat messages
- `scheduled_tasks` - Task execution audit log
- `generated_images` - DALL-E image metadata
- `bot_config` - Dynamic configuration storage

---

## Testing (`tests/`)

Comprehensive test coverage for bot functionality.

### Structure

```text
tests/
├── unit/                              # Unit tests (isolated)
│   └── services/
│       ├── test_llm_service.py
│       ├── test_persona_service.py
│       ├── test_command_service.py
│       └── test_engagement_service.py
│
├── integration/                       # Integration tests (multi-component)
│   ├── handlers/
│   │   ├── test_message_handler.py
│   │   ├── test_command_handler.py
│   │   └── test_thread_handler.py
│   └── services/
│       ├── test_mcp_integration.py
│       └── test_scheduler_integration.py
│
├── fixtures/                          # Test data and mocks
│   ├── slack_events.py               # Mock Slack events
│   ├── database_fixtures.py          # Test database setup
│   └── mcp_responses.py              # Mock MCP responses
│
└── helpers/                           # Test utilities
    ├── assertions.py                 # Custom assertions
    └── mocks.py                      # Mock objects
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/services/test_llm_service.py

# Run tests matching pattern
pytest -k "test_command"

# Run with verbose output
pytest -v

# Run only integration tests
pytest tests/integration/

# Run only unit tests
pytest tests/unit/
```

### Test Configuration

Configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--tb=short",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
]
```

**Coverage Reports**: Generated in `htmlcov/` directory

---

## Key Files

### Root Level Configuration

#### `pyproject.toml`
**Purpose**: Python project metadata and dependencies.

**Key Sections**:
- `[project]` - Package metadata
- `dependencies` - Runtime dependencies
- `[project.optional-dependencies]` - Development dependencies
- `[tool.pytest.ini_options]` - Test configuration
- `[tool.ruff]` - Linting configuration

#### `.env` (not committed)
**Purpose**: Environment variables and secrets.

**Required Variables**:
```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Dashboard Authentication
DASHBOARD_SECRET_KEY=random-secret-key
DASHBOARD_ADMIN_PASSWORD=secure-password

# MCP Server URLs (Docker internal)
MCP_WEB_SEARCH_URL=http://web-search-mcp-dev:9765/sse
MCP_SLACK_OPS_URL=http://localhost:9766/sse

# Bot API URL (Dashboard → Bot communication)
BOT_API_URL=http://lukas-bear-bot-dev:5001
```

**⚠️ Security**: Never commit `.env` file. Use `.env.example` as template.

#### `.env.example`
**Purpose**: Template for environment variables.

**Usage**: Copy to `.env` and fill in actual values:
```bash
cp .env.example .env
```

#### `alembic.ini`
**Purpose**: Alembic migration configuration.

**Key Settings**:
- `sqlalchemy.url` - Database connection string
- `script_location` - Migration scripts directory
- Logging configuration

#### `README.md`
**Purpose**: Project overview and quick start guide.

**Contents**:
- Project description
- Features list
- Quick start instructions
- Development setup
- Architecture overview

#### `CLAUDE.md`
**Purpose**: Development guidelines for AI assistants.

**Contents**:
- Active technologies
- Project structure summary
- Code style guidelines
- Recent changes
- Common commands
- MCP architecture notes

**Auto-generated**: Updated when new features are implemented

#### `CHANGELOG.md`
**Purpose**: Record of notable changes and releases.

**Format**: Keep a Changelog standard

**Sections per version**:
- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

---

## Quick Reference

### Start Development Environment

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker logs lukas-bear-bot-dev -f
docker logs dashboard-dev -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Access Services

- **Dashboard**: http://localhost:8080
- **Frontend Dev Server**: http://localhost:5173
- **Bot**: Socket Mode (no HTTP access)
- **MCP Servers**: Internal Docker network only

### Common Development Tasks

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Apply database migrations
docker exec lukas-bear-bot-dev alembic upgrade head

# Create new migration
docker exec lukas-bear-bot-dev alembic revision --autogenerate -m "description"

# Check code style
ruff check .

# Format code
ruff format .
```

---

## Additional Documentation

- **API Documentation**: See `docs/API.md` (if exists)
- **MCP Integration**: See `MCP_INTEGRATION_STATUS.md`
- **Feature Specs**: See `specs/` directory
- **Migration Guide**: See `CHANGELOG.md`

---

**Last Updated**: 2025-10-29
**Version**: 1.0.0
