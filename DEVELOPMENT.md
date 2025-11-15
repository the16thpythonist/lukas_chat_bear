# Development Guide

This guide provides detailed instructions for setting up the development environment and contributing to the Lukas the Bear chatbot project.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Development Workflow](#development-workflow)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Database Management](#database-management)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [Common Issues](#common-issues)
- [Contributing](#contributing)

---

## Prerequisites

### Required Software

- **Python** 3.11 or higher
- **Docker** 20.10+ and Docker Compose 2.0+
- **Git** 2.30+
- **Node.js** 18+ (for web-search MCP server)

### Optional Tools

- **VS Code** with Python extension
- **Postman** or **curl** for API testing
- **Redis** (for production session storage)

### System Requirements

- **OS**: Linux, macOS, or Windows (with WSL2 for Docker)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk**: 5GB free space for Docker images and data

---

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/lukas_chat_bear.git
cd lukas_chat_bear
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -e ".[dev]"
```

**Development Dependencies Include**:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `ruff` - Fast Python linter and formatter

### 3. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values
nano .env  # or your preferred editor
```

**Required Environment Variables**:

```bash
# === Slack Configuration ===
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# === OpenAI Configuration ===
OPENAI_API_KEY=sk-your-openai-key

# === Dashboard Authentication ===
DASHBOARD_SECRET_KEY=generate-random-32-char-string
DASHBOARD_ADMIN_PASSWORD=your-secure-password

# === MCP Server URLs (Docker internal) ===
MCP_WEB_SEARCH_URL=http://web-search-mcp-dev:9765/sse
MCP_SLACK_OPS_URL=http://localhost:9766/sse
MCP_SLACK_OPS_HOST=0.0.0.0
MCP_SLACK_OPS_PORT=9766

# === Bot API URL (Dashboard → Bot communication) ===
BOT_API_URL=http://lukas-bear-bot-dev:5001
INTERNAL_API_PORT=5001

# === Feature Flags ===
USE_MCP_AGENT=true
```

**How to Get API Keys**:

1. **Slack Bot Token**:
   - Go to https://api.slack.com/apps
   - Create new app or select existing
   - Navigate to "OAuth & Permissions"
   - Install app to workspace
   - Copy "Bot User OAuth Token"

2. **Slack App Token**:
   - In same Slack app settings
   - Navigate to "Basic Information"
   - Scroll to "App-Level Tokens"
   - Generate token with `connections:write` scope
   - Copy token

3. **OpenAI API Key**:
   - Go to https://platform.openai.com/api-keys
   - Create new secret key
   - Copy key (only shown once!)

### 4. Build Docker Images

```bash
# Build all services
docker-compose -f docker-compose.dev.yml build

# This will:
# - Build bot container (Python 3.11 + dependencies)
# - Build dashboard container (Python backend + Node.js frontend)
# - Pull web-search-mcp image
```

**First Build Notes**:
- May take 5-10 minutes
- Downloads ~2GB of images and dependencies
- Requires stable internet connection

---

## Development Workflow

### Daily Development Cycle

```bash
# 1. Start development services
docker-compose -f docker-compose.dev.yml up -d

# 2. Watch logs (optional)
docker logs lukas-bear-bot-dev -f

# 3. Make code changes
# - Bot code: Changes reflected after container restart
# - Dashboard backend: Auto-reload (Flask debug mode)
# - Dashboard frontend: Hot Module Replacement (Vite)

# 4. Restart bot after changes
docker-compose -f docker-compose.dev.yml restart lukas-bot

# 5. Stop services when done
docker-compose -f docker-compose.dev.yml down
```

### Making Changes

#### Bot Changes (Python)

1. Edit files in `src/`
2. Restart bot container:
   ```bash
   docker-compose -f docker-compose.dev.yml restart lukas-bot
   ```
3. Check logs for errors:
   ```bash
   docker logs lukas-bear-bot-dev -f
   ```

**Live Reload**: Not available for bot. Must restart container.

#### Dashboard Backend Changes (Python)

1. Edit files in `dashboard/backend/`
2. **No restart needed** - Flask debug mode auto-reloads
3. Check logs:
   ```bash
   docker logs dashboard-dev -f
   ```

**Live Reload**: Enabled via Flask debug mode.

#### Dashboard Frontend Changes (Vue.js)

1. Edit files in `dashboard/frontend/src/`
2. **No restart needed** - Vite HMR updates browser instantly
3. Check browser console for errors
4. Access at http://localhost:5173

**Hot Module Replacement**: Enabled via Vite dev server.

### Creating New Features

1. **Plan the feature**:
   ```bash
   # Use Specify framework if available
   /speckit.specify "Feature description"
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Implement feature**:
   - Write code following project structure
   - Add tests for new functionality
   - Update configuration if needed

4. **Test locally**:
   ```bash
   # Run tests
   pytest

   # Check code quality
   ruff check .

   # Test in Docker environment
   docker-compose -f docker-compose.dev.yml up
   ```

5. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: Add your feature description"
   ```

6. **Create pull request**:
   ```bash
   git push origin feature/your-feature-name
   # Then create PR on GitHub
   ```

---

## Running the Application

### Development Mode (Recommended)

```bash
# Start all services with live reload
docker-compose -f docker-compose.dev.yml up -d

# Access services:
# - Dashboard: http://localhost:8080
# - Frontend Dev Server: http://localhost:5173
# - Bot: Socket Mode (no HTTP access)
```

**What's Running**:
- ✅ Bot container (Socket Mode)
- ✅ MCP Server (port 9766, internal)
- ✅ Internal API (port 5001, internal)
- ✅ Dashboard backend (port 8080)
- ✅ Dashboard frontend (port 5173, HMR)
- ✅ Web Search MCP (port 9765, internal)

### Production Mode (Testing)

```bash
# Build production images
docker-compose build

# Start production services
docker-compose up -d

# Access dashboard: http://localhost:8080
```

**Differences from Development**:
- No live reload
- Frontend built and served by backend
- Optimized images (smaller size)
- Production logging levels

### Local Development (Without Docker)

**Not recommended** - MCP servers require Docker networking.

If you must run locally:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run database migrations
alembic upgrade head

# Start bot
python -m src.bot

# In separate terminal, start MCP server
python -m src.mcp_server

# In separate terminal, start Internal API
python -m src.api.internal_api

# In separate terminal, start Dashboard backend
cd dashboard/backend
python -m flask run --port 8080

# In separate terminal, start Dashboard frontend
cd dashboard/frontend
npm run dev
```

**⚠️ Limitations**:
- MCP server URLs need adjustment
- Web Search MCP won't work (requires Docker)
- Complex process management

---

## Testing

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/services/test_llm_service.py

# Run tests matching pattern
pytest -k "test_command"

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Coverage Goals**:
- **Overall**: 80%+ coverage
- **Critical Services**: 90%+ coverage
- **Handlers**: 75%+ coverage

### Writing Tests

#### Unit Test Example

```python
# tests/unit/services/test_persona_service.py
import pytest
from src.services.persona_service import PersonaService

def test_get_greeting_returns_string():
    """Test that greeting template is returned as string."""
    service = PersonaService()
    greeting = service.get_greeting_template()

    assert isinstance(greeting, str)
    assert len(greeting) > 0

@pytest.mark.asyncio
async def test_async_service_call():
    """Test async service method."""
    service = MyAsyncService()
    result = await service.async_method()

    assert result is not None
```

#### Integration Test Example

```python
# tests/integration/services/test_mcp_integration.py
import pytest
from src.services.llm_agent_service import LLMAgentService

@pytest.mark.asyncio
async def test_mcp_agent_can_call_tools():
    """Test that agent can call MCP tools."""
    service = LLMAgentService()
    await service.initialize_mcp()

    response = await service.generate_response(
        conversation_messages=[],
        user_message="What's the weather in San Francisco?",
        user_id="U123456"
    )

    assert response is not None
    assert len(response) > 0
```

### Test Fixtures

Located in `tests/fixtures/`:

```python
# tests/fixtures/database_fixtures.py
import pytest
from src.utils.database import session_scope
from src.models.team_member import TeamMember

@pytest.fixture
def test_user(db_session):
    """Create test user in database."""
    user = TeamMember(
        slack_user_id="U123456",
        display_name="Test User",
        real_name="Test User"
    )
    db_session.add(user)
    db_session.commit()

    yield user

    db_session.delete(user)
    db_session.commit()
```

---

## Database Management

### Migrations

Using Alembic for database versioning:

```bash
# Apply all pending migrations
alembic upgrade head

# Create new migration (auto-detect changes)
alembic revision --autogenerate -m "Add new column"

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history --verbose
```

### Migration Workflow

1. **Modify SQLAlchemy models** in `src/models/`

2. **Generate migration**:
   ```bash
   alembic revision --autogenerate -m "Descriptive message"
   ```

3. **Review generated migration** in `migrations/versions/`
   - Check `upgrade()` function
   - Check `downgrade()` function
   - Verify SQL operations are correct

4. **Apply migration**:
   ```bash
   alembic upgrade head
   ```

5. **Test migration**:
   - Verify schema changes in database
   - Test application functionality
   - Test rollback: `alembic downgrade -1`

6. **Commit migration file**:
   ```bash
   git add migrations/versions/xxx_your_migration.py
   git commit -m "chore: Add migration for new feature"
   ```

### Database Access

#### In Docker Container

```bash
# Access SQLite database
docker exec -it lukas-bear-bot-dev sqlite3 /app/data/lukas.db

# Example queries
sqlite> .tables
sqlite> SELECT * FROM team_members LIMIT 5;
sqlite> .exit
```

#### Local Database

```bash
# Access local database
sqlite3 data/lukas.db

# Or use GUI tool like DB Browser for SQLite
```

### Resetting Database

```bash
# ⚠️ WARNING: This will delete all data!

# Stop containers
docker-compose -f docker-compose.dev.yml down

# Delete database file
rm data/lukas.db

# Start containers (migrations run automatically)
docker-compose -f docker-compose.dev.yml up -d
```

---

## Code Quality

### Linting

Using **Ruff** - Fast Python linter and formatter:

```bash
# Check code style
ruff check .

# Check specific file
ruff check src/services/llm_service.py

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Configuration**: Defined in `pyproject.toml`

```toml
[tool.ruff]
line-length = 100
select = ["E", "W", "F", "I", "B", "UP"]
ignore = ["E501"]  # Line too long - we use 100 but allow flexibility
target-version = "py311"
```

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Set up git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Code Style Guidelines

**Python**:
- Follow PEP 8 with 100-character line length
- Use type hints where possible
- Docstrings for all public functions/classes
- Use async/await for I/O operations

**Example**:
```python
from typing import Optional, List
from src.models.message import Message

async def process_messages(
    messages: List[Message],
    user_id: Optional[str] = None
) -> str:
    """
    Process conversation messages and generate response.

    Args:
        messages: List of message objects
        user_id: Optional Slack user ID for context

    Returns:
        Generated response text

    Raises:
        ValueError: If messages list is empty
    """
    if not messages:
        raise ValueError("Messages list cannot be empty")

    # Implementation
    return response
```

---

## Debugging

### Viewing Logs

```bash
# Bot logs
docker logs lukas-bear-bot-dev -f

# Dashboard logs
docker logs dashboard-dev -f

# Web Search MCP logs
docker logs web-search-mcp-dev -f

# All logs combined
docker-compose -f docker-compose.dev.yml logs -f

# Logs since specific time
docker logs lukas-bear-bot-dev --since 10m

# Last 50 lines
docker logs lukas-bear-bot-dev --tail 50
```

### Interactive Debugging

#### Python Debugger (pdb)

Add breakpoint in code:
```python
import pdb; pdb.set_trace()
```

Attach to container:
```bash
docker attach lukas-bear-bot-dev
```

**⚠️ Note**: Container must be run with `-it` flags for interactive debugging.

#### Remote Debugging (VS Code)

1. Install Python extension in VS Code
2. Add to `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Remote Attach",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/app"
        }
      ]
    }
  ]
}
```

3. Install `debugpy` in container
4. Start bot with debug server
5. Attach VS Code debugger

### Common Debug Scenarios

#### Bot Not Responding to Messages

1. Check Slack connection:
   ```bash
   docker logs lukas-bear-bot-dev | grep "Bolt app is running"
   ```

2. Verify Socket Mode token:
   ```bash
   docker exec lukas-bear-bot-dev env | grep SLACK_APP_TOKEN
   ```

3. Check handler registration:
   ```bash
   docker logs lukas-bear-bot-dev | grep "handlers registered"
   ```

#### MCP Tools Not Working

1. Check MCP server connection:
   ```bash
   docker logs lukas-bear-bot-dev | grep "MCP"
   ```

2. Verify MCP endpoints:
   ```bash
   docker exec lukas-bear-bot-dev curl http://localhost:9766/sse
   docker exec lukas-bear-bot-dev curl http://web-search-mcp-dev:9765/sse
   ```

3. Check agent initialization:
   ```bash
   docker logs lukas-bear-bot-dev | grep "agent"
   ```

#### Dashboard Can't Connect to Bot

1. Check bot internal API:
   ```bash
   docker exec dashboard-dev curl http://lukas-bear-bot-dev:5001/api/internal/health
   ```

2. Verify network connectivity:
   ```bash
   docker exec dashboard-dev ping lukas-bear-bot-dev
   ```

3. Check environment variable:
   ```bash
   docker exec dashboard-dev env | grep BOT_API_URL
   ```

---

## Common Issues

### Issue: Port Already in Use

**Symptoms**: `Error: bind: address already in use`

**Solution**:
```bash
# Find process using port
lsof -i :8080
# or
netstat -tulpn | grep 8080

# Kill process
kill -9 <PID>

# Or use different port in docker-compose.dev.yml
```

### Issue: Database Locked

**Symptoms**: `database is locked` error

**Solution**:
```bash
# Stop all containers
docker-compose -f docker-compose.dev.yml down

# Restart with clean slate
docker-compose -f docker-compose.dev.yml up -d
```

**Cause**: SQLite doesn't support concurrent writes well.

### Issue: Docker Build Fails

**Symptoms**: Build fails with dependency errors

**Solution**:
```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker-compose -f docker-compose.dev.yml build --no-cache
```

### Issue: Hot Reload Not Working

**Dashboard Frontend**:
1. Verify Vite dev server is running on port 5173
2. Check browser console for connection errors
3. Restart dashboard container

**Dashboard Backend**:
1. Verify Flask debug mode is enabled
2. Check for syntax errors in logs
3. Restart may be needed for dependency changes

### Issue: MCP ReadTimeout Errors

**Symptoms**: `httpx.ReadTimeout` in logs

**Solution**: This is normal for idle connections. The timeout is set to 1 hour and connections automatically reconnect.

**If persistent**:
- Check MCP server health
- Verify Docker networking
- Check firewall rules

---

## Contributing

### Branching Strategy

```
main                    # Production-ready code
├── develop            # Development integration branch
    ├── feature/xyz    # New features
    ├── bugfix/xyz     # Bug fixes
    └── hotfix/xyz     # Urgent production fixes
```

### Commit Message Convention

Follow Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(dashboard): Add user targeting for manual DM control

Allows dashboard users to select specific team member for DM
instead of random selection. Updates bot API to support
targeted DM via user_id parameter.

Closes #123
```

```
fix(mcp): Increase SSE connection timeout to prevent errors

Changed MCP client timeout from 5s to 3600s to prevent
httpx.ReadTimeout during idle periods.
```

### Pull Request Process

1. **Create feature branch**
2. **Make changes with tests**
3. **Run quality checks**:
   ```bash
   pytest
   ruff check .
   ```
4. **Commit with conventional message**
5. **Push and create PR**
6. **Wait for CI/CD checks** (if configured)
7. **Address review feedback**
8. **Merge after approval**

### Code Review Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Docstrings added/updated
- [ ] Type hints used where applicable
- [ ] No hardcoded secrets
- [ ] Database migrations included (if schema changed)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if user-facing change)

---

## Useful Resources

### Documentation
- [Slack Bolt Python](https://slack.dev/bolt-python/)
- [OpenAI API](https://platform.openai.com/docs)
- [LangChain](https://python.langchain.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Vue.js 3](https://vuejs.org/)
- [Vite](https://vitejs.dev/)

### Internal Docs
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Project organization
- [API.md](docs/API.md) - API documentation
- [CHANGELOG.md](CHANGELOG.md) - Version history

### Community
- Slack workspace: [Your workspace]
- Issue tracker: [GitHub Issues]
- Discussions: [GitHub Discussions]

---

**Last Updated**: 2025-10-29
**Maintainer**: Development Team
