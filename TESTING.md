# Testing Guide for Lukas the Bear Slack Bot

This document provides comprehensive instructions for testing the Lukas the Bear Slack bot project.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Infrastructure](#test-infrastructure)
- [Running Tests](#running-tests)
- [Dashboard Testing](#dashboard-testing)
- [Test Organization](#test-organization)
- [Writing New Tests](#writing-new-tests)
- [Docker Testing](#docker-testing)
- [Coverage Reporting](#coverage-reporting)
- [Environment Setup](#environment-setup)
- [Troubleshooting](#troubleshooting)
- [Testing Gaps](#testing-gaps)

---

## Quick Start

### Prerequisites

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if not already installed)
pip install -e .
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with detailed output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/services/test_command_service.py

# Tests matching a pattern
pytest -k "test_command"
```

### Run Dashboard Tests

```bash
# Navigate to dashboard
cd dashboard

# Run all dashboard tests (backend by default)
./run-tests.sh

# Run with coverage
./run-tests.sh --coverage

# Frontend tests
./run-tests.sh --frontend-only
```

See the [Dashboard Testing](#dashboard-testing) section for complete details.

---

## Test Infrastructure

### Test Statistics

- **Total test files:** 21 test files
- **Total test functions:** ~326 test functions
- **Total test code:** ~8,268 lines
- **Source files:** 33 Python files
- **Test coverage ratio:** ~64% (21 test files for 33 source files)

### Testing Frameworks & Tools

#### Core Testing Libraries

- **pytest** (7.4.3+) - Main testing framework
- **pytest-asyncio** (0.21.1+) - Async test support
- **pytest-cov** (4.1.0+) - Coverage reporting
- **pytest-mock** (3.12.0+) - Mocking utilities

#### Additional Test Dependencies

- **freezegun** - Time mocking for scheduler tests
- **unittest.mock** - Python standard mocking library
- **SQLAlchemy test utilities** - Database fixtures

### Pytest Configuration

Configuration is defined in `pyproject.toml`:

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

### Coverage Goals

- **Overall:** 80%+
- **Critical services:** 90%+
- **Handlers:** 75%+

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with extra verbosity (show test names)
pytest -vv

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/services/test_command_service.py

# Run specific test function
pytest tests/unit/test_models.py::test_team_member_creation

# Run tests matching pattern
pytest -k "command_service"

# Run tests with specific marker
pytest -m asyncio

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### Test Categories

```bash
# Unit tests (isolated, mocked dependencies)
pytest tests/unit/

# Integration tests (end-to-end, real dependencies)
pytest tests/integration/

# Model tests
pytest tests/unit/models/

# Repository tests
pytest tests/unit/repositories/

# Service tests
pytest tests/unit/services/

# Handler integration tests
pytest tests/integration/handlers/
```

### Running Tests with Different Output Formats

```bash
# Minimal output
pytest -q

# Show test durations
pytest --durations=10

# Show slowest tests
pytest --durations=0

# Generate JUnit XML report
pytest --junit-xml=report.xml

# Disable warnings
pytest --disable-warnings
```

---

## Dashboard Testing

The dashboard has its own separate test suite for both backend (Flask/Python) and frontend (Vue/JavaScript) components.

### Quick Start

```bash
# Run all dashboard tests (backend only by default)
cd dashboard
./run-tests.sh

# Run backend tests only
./run-tests.sh --backend-only

# Run frontend tests only
./run-tests.sh --frontend-only

# Run with coverage
./run-tests.sh --coverage

# Run only unit tests
./run-tests.sh --unit

# Run only integration tests
./run-tests.sh --integration
```

### Dashboard Test Structure

```text
dashboard/
├── backend/
│   ├── tests/
│   │   ├── unit/
│   │   │   └── test_query_builder.py      # Query, pagination, filtering
│   │   └── integration/
│   │       ├── test_auth_api.py           # Authentication endpoints
│   │       └── test_events_api.py         # Events API endpoints
│   └── requirements.txt                    # Includes pytest, pytest-flask
└── frontend/
    ├── tests/
    │   ├── unit/                           # Component & utility tests
    │   └── e2e/                            # Playwright E2E tests
    └── package.json                        # Includes vitest, @vue/test-utils
```

### Backend Dashboard Tests

```bash
# Navigate to dashboard backend
cd dashboard/backend

# Run all backend tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/unit/test_query_builder.py

# Run integration tests only
pytest tests/integration/
```

**Backend Test Coverage:**
- ✅ Query builders (pagination, filtering, date ranges)
- ✅ Authentication API (login, logout, session)
- ✅ Events API (upcoming, completed)
- ✅ Activity log API
- ✅ Images API

### Frontend Dashboard Tests

```bash
# Navigate to dashboard frontend
cd dashboard/frontend

# Install dependencies (if needed)
npm install

# Run unit tests
npm run test:unit

# Run E2E tests
npm run test:e2e

# Run tests in watch mode
npm run test:unit -- --watch
```

**Frontend Test Coverage:**
- ✅ Vue component rendering
- ✅ Date formatting utilities
- ✅ API service calls
- ✅ User workflows (E2E)

### Dashboard Testing Tools

**Backend:**
- `pytest` - Test framework
- `pytest-flask` - Flask testing helpers
- `pytest-cov` - Coverage reporting

**Frontend:**
- `vitest` - Fast unit test runner
- `@vue/test-utils` - Vue component testing
- `@playwright/test` - E2E browser testing

### Dashboard Test Examples

**Backend Unit Test:**
```python
def test_paginate_first_page(db_session, sample_messages):
    """Test pagination returns correct first page."""
    from backend.models import Message

    query = db_session.query(Message)
    result = paginate(query, page=1, limit=5)

    assert result['page'] == 1
    assert len(result['items']) == 5
    assert result['total'] == 20
```

**Backend Integration Test:**
```python
def test_auth_login_success(client):
    """Test successful login returns auth token."""
    response = client.post('/api/auth/login', json={
        'password': 'dev_password_123'
    })

    assert response.status_code == 200
    assert 'token' in response.json
```

**Frontend Unit Test:**
```javascript
import { describe, it, expect } from 'vitest'
import { formatDateTime } from '@/utils/date'

describe('formatDateTime', () => {
  it('formats date correctly', () => {
    const result = formatDateTime('2025-10-28T21:00:00')
    expect(result).toBe('10/28/2025, 21:00:47')
  })
})
```

### Detailed Dashboard Documentation

For comprehensive dashboard testing documentation, see:
- **[dashboard/TESTING.md](dashboard/TESTING.md)** - Complete testing strategy, test pyramid, coverage goals, CI/CD integration

---

## Test Organization

### Directory Structure

```text
tests/
├── conftest.py                        # Main fixtures (DB, mocks, seeded data)
├── helpers/
│   └── scheduler_helpers.py          # Scheduler test utilities
├── unit/                              # Unit tests (isolated, mocked)
│   ├── models/
│   │   └── test_scheduled_event.py   # SQLAlchemy model tests
│   ├── repositories/
│   │   ├── test_config_repo.py
│   │   ├── test_conversation_repo.py
│   │   ├── test_scheduled_event_repo.py
│   │   └── test_team_member_repo.py
│   ├── services/
│   │   ├── test_command_service.py   # CommandService business logic
│   │   ├── test_engagement_service.py
│   │   ├── test_image_service.py
│   │   ├── test_llm_agent_service.py # MCP agent fallbacks
│   │   └── test_scheduled_event_service.py
│   ├── test_alembic.py               # Database migrations
│   ├── test_database.py              # Core DB functionality
│   ├── test_engagement_logic.py
│   └── test_models.py                # All SQLAlchemy models
└── integration/                       # Integration tests (end-to-end)
    ├── handlers/
    │   └── test_thread_handler_integration.py
    ├── services/
    │   ├── test_random_dm_scheduler.py
    │   ├── test_random_dm_timing.py
    │   ├── test_random_dm_workflow.py
    │   └── test_scheduler_integration.py
    ├── test_image_generation.py      # DALL-E integration
    └── test_mcp_integration.py        # MCP server connections
```

### Test Fixtures

#### Main Fixtures (`tests/conftest.py`)

**Database Fixtures:**
- `test_db_path` - Temporary SQLite database file
- `test_engine` - SQLAlchemy engine with WAL mode, foreign keys enabled
- `test_session` - Auto-rollback session for test isolation
- `seeded_db` - Pre-populated database with realistic test data

**Mock Fixtures:**
- `mock_slack_client` - Mocked Slack WebClient
- `mock_slack_app` - Mocked Slack Bolt App
- `mock_slack_client_for_dm` - DM-specific mocks
- `engagement_team_members` - 7 realistic team members
- `engagement_config` - Pre-configured settings
- `sample_thread_messages` - Slack thread conversation data

**Repository Fixtures:**
- `conversation_repo` - ConversationRepository instance
- `team_member_repo` - TeamMemberRepository instance
- `config_repo` - ConfigurationRepository instance

**Service Fixtures:**
- `engagement_service_instance` - Real EngagementService
- `proactive_dm_service` - ProactiveDMService instance

---

## Writing New Tests

### Unit Test Pattern

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_post_message_success(command_service, mock_regular_user, mock_slack_client):
    """Test successful message posting."""
    # Setup - Arrange
    command_service.team_member_repo.get_by_slack_user_id = Mock(
        return_value=mock_regular_user
    )
    mock_slack_client.chat_postMessage.return_value = {"ok": True}

    # Execute - Act
    result = await command_service.post_message(
        message="Test message",
        channel="general",
        user_id="U_USER"
    )

    # Assert
    assert result["success"] is True
    assert "Posted message" in result["message"]
    mock_slack_client.chat_postMessage.assert_called_once_with(
        channel="#general",
        text="Test message"
    )
```

### Integration Test Pattern

```python
import pytest
import os

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("MCP_WEB_SEARCH_URL"),
    reason="MCP server not configured, skipping live test",
)
async def test_live_mcp_connection():
    """LIVE TEST: Connect to actual MCP server if available."""
    from src.services.llm_agent_service import LLMAgentService

    service = LLMAgentService()
    await service.initialize_mcp()

    assert len(service.mcp_tools) > 0
    assert any("search" in tool.name for tool in service.mcp_tools)

    await service.cleanup()
```

### Database Test Pattern

```python
from sqlalchemy.orm import Session
from src.models.team_member import TeamMember

def test_create_team_member(test_session: Session):
    """Test creating a basic team member record."""
    # Arrange
    member = TeamMember(
        slack_user_id="U12345",
        display_name="John Doe",
        real_name="John Doe",
        is_bot=False
    )

    # Act
    test_session.add(member)
    test_session.commit()

    # Assert
    assert member.id is not None
    assert member.slack_user_id == "U12345"
    assert member.display_name == "John Doe"
```

### Async Mocking Pattern

```python
from unittest.mock import AsyncMock, Mock
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function with mocked dependencies."""
    # Create async mock
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = "Mocked response"

    # Use in test
    result = await mock_llm.generate_response("test prompt")

    assert result == "Mocked response"
    mock_llm.generate_response.assert_awaited_once_with("test prompt")
```

### Time Mocking Pattern

```python
from freezegun import freeze_time
from datetime import datetime

@freeze_time("2025-01-15 10:30:00")
def test_scheduled_event_timing():
    """Test event scheduling with frozen time."""
    now = datetime.now()
    assert now.hour == 10
    assert now.minute == 30
```

### Test Naming Conventions

- **Test files:** `test_<module_name>.py`
- **Test functions:** `test_<functionality>_<scenario>()`
- **Test classes:** `Test<ClassName>`

**Examples:**
- `test_post_message_success()`
- `test_post_message_permission_denied()`
- `test_create_reminder_invalid_time_format()`

### Documentation Pattern

```python
def test_example():
    """Test short description.

    This test verifies that [specific behavior] works correctly
    when [specific conditions].

    Protects against: [specific bug or regression]
    """
    # Test implementation
```

---

## Docker Testing

### Running Tests in Docker Container

```bash
# Start dev containers
docker-compose -f docker-compose.dev.yml up -d

# Run all tests in container
docker exec -it lukas-bear-bot-dev pytest

# Run specific test file
docker exec -it lukas-bear-bot-dev pytest tests/unit/test_models.py

# Run with coverage
docker exec -it lukas-bear-bot-dev pytest --cov=src --cov-report=html

# Interactive shell in container
docker exec -it lukas-bear-bot-dev bash
# Then run: pytest
```

### Docker Test Environment

The dev container (`docker-compose.dev.yml`) provides:

- **Live code mounting:** `./src` → `/app/src` (changes reflected immediately)
- **Test file mounting:** `./tests` → `/app/tests`
- **MCP server access:** Web Search MCP on port 9765
- **Database isolation:** Tests use temporary SQLite files
- **Environment variables:** Pre-configured for testing

### MCP Integration Tests

Integration tests require MCP servers running:

```bash
# Start all services including MCP servers
docker-compose -f docker-compose.dev.yml up -d

# Check MCP server status
docker logs web-search-mcp-dev

# Run integration tests
pytest tests/integration/test_mcp_integration.py
```

**Skip live tests if servers unavailable:**

Tests are automatically skipped if MCP servers aren't configured:

```python
@pytest.mark.skipif(
    not os.getenv("MCP_WEB_SEARCH_URL"),
    reason="MCP server not configured, skipping live test",
)
```

---

## Coverage Reporting

### Generate Coverage Reports

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html

# Generate terminal report with missing lines
pytest --cov=src --cov-report=term-missing

# Generate XML report (for CI/CD)
pytest --cov=src --cov-report=xml

# Combine multiple report formats
pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
```

### View Coverage Reports

```bash
# Open HTML coverage report
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html      # macOS

# View in terminal
pytest --cov=src --cov-report=term
```

### Coverage Report Files

- **`.coverage`** - Binary coverage data file
- **`htmlcov/`** - HTML coverage report directory
- **`coverage.xml`** - XML coverage report (for CI/CD tools)

### Interpreting Coverage Reports

**HTML Report:**
- **Green lines:** Covered by tests
- **Red lines:** Not covered by tests
- **Orange lines:** Partially covered (e.g., branch not taken)

**Terminal Report:**
```
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
src/services/command.py       145      8    94%   23-25, 89-92
src/handlers/message.py       234     89    62%   45-67, 123-156
```

- **Stmts:** Total statements
- **Miss:** Statements not covered
- **Cover:** Coverage percentage
- **Missing:** Line numbers not covered

---

## Environment Setup

### Minimal Setup (Unit Tests)

Unit tests use mocked dependencies and don't require real API keys:

```bash
# .env.test (optional - for testing convenience)
OPENAI_API_KEY=test-key-not-real
SLACK_BOT_TOKEN=xoxb-test-token
SLACK_APP_TOKEN=xapp-test-token
```

### Full Setup (Integration Tests)

Integration tests require real services:

```bash
# Required for integration tests
SLACK_BOT_TOKEN=xoxb-your-real-bot-token
SLACK_APP_TOKEN=xapp-your-real-app-token
OPENAI_API_KEY=sk-your-real-openai-key

# MCP server URLs (when running Docker)
MCP_WEB_SEARCH_URL=http://web-search-mcp-dev:9765/sse
MCP_SLACK_OPS_URL=http://localhost:9766/sse

# Optional
USE_MCP_AGENT=true
LOG_LEVEL=DEBUG
```

### Database Setup

Tests automatically handle database setup:

- **Temporary SQLite files** created per test session
- **Schema auto-created** via `Base.metadata.create_all()`
- **Auto-cleanup** after tests complete
- **No manual setup required**

### Running Tests Without API Keys

```bash
# Run only unit tests (no API calls)
pytest tests/unit/

# Skip integration tests
pytest --ignore=tests/integration/
```

