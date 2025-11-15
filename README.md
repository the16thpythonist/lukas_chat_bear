# Lukas the Bear - Slack Chatbot 🐻

A friendly AI-powered Slack chatbot with Model Context Protocol (MCP) integration and web-based admin dashboard.

## ✨ Features

### Core Capabilities
- **🤖 AI Conversations**: Natural language chat powered by GPT with MCP tool access
- **🔧 Smart Commands**: Execute complex actions via natural language (no exact syntax required)
- **🎨 Image Generation**: DALL-E powered bear-themed artwork
- **📊 Web Dashboard**: Monitor analytics, view history, and trigger manual actions
- **🔍 Web Search**: Integrated web search capabilities via MCP
- **⏰ Proactive Engagement**: Scheduled DMs and channel participation
- **🎭 Consistent Personality**: Warm, encouraging bear persona across all interactions

### MCP Integration (Model Context Protocol)
Lukas uses the MCP standard for tool integration:
- **Slack Operations** (5 tools): Post messages, create reminders, manage configuration
- **Web Search** (3 tools): Full web search, summaries, single page extraction
- **Natural Language Processing**: No exact command syntax - just ask naturally!

### Web Dashboard
- **Analytics Overview**: Message counts, user engagement, activity trends
- **Manual Controls**: Trigger image generation and DMs on-demand
- **Image Gallery**: Browse all generated DALL-E images
- **Task History**: Audit log of all scheduled and manual actions
- **Session Authentication**: Secure access with password protection

---

## 📚 Documentation

### Getting Started
- **[Quick Start](#quick-start)** - Get up and running in 5 minutes
- **[Development Guide](DEVELOPMENT.md)** - Comprehensive developer setup and workflow
- **[Configuration](#configuration)** - Customize bot behavior

### Technical Documentation
- **[Architecture Overview](ARCHITECTURE.md)** - System design, patterns, and decisions
- **[Project Structure](PROJECT_STRUCTURE.md)** - Directory organization and key files
- **[API Documentation](docs/API.md)** - Complete API reference (Dashboard & Bot)

### Feature Specifications
- **[Core Bot Spec](specs/001-lukas-bear-chatbot/)** - Original chatbot feature design
- **[Dashboard Spec](specs/002-web-dashboard/)** - Web dashboard feature design

### Status & Migrations
- **[MCP Integration Status](MCP_INTEGRATION_STATUS.md)** - MCP setup and tool catalog
- **[MCP Command Migration](MCP_COMMAND_MIGRATION_COMPLETE.md)** - Regex → NLP migration
- **[Changelog](CHANGELOG.md)** - Version history and notable changes

---

## 🚀 Quick Start

### Prerequisites

- **Docker** & Docker Compose v2.0+
- **Slack workspace** with admin access
- **OpenAI API key** (for GPT and DALL-E)

### Setup (5 minutes)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd lukas_chat_bear
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   Required variables:
   ```bash
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_APP_TOKEN=xapp-your-token
   OPENAI_API_KEY=sk-your-key
   DASHBOARD_ADMIN_PASSWORD=your-secure-password
   ```

3. **Create Slack app**:
   - Visit https://api.slack.com/apps
   - Create new app from manifest or manually configure
   - Enable Socket Mode with `connections:write` scope
   - Add OAuth scopes: `chat:write`, `im:history`, `im:read`, `channels:history`, etc.
   - Install app to workspace

4. **Start services**:
   ```bash
   # Development mode (with live reload)
   docker-compose -f docker-compose.dev.yml up -d

   # Production mode
   docker-compose up -d
   ```

5. **Access dashboard**:
   - Open http://localhost:8080
   - Login with password from `.env`

6. **Test in Slack**:
   - Send DM to Lukas: "Hi Lukas!"
   - Try a command: "Remind me in 30 minutes to check the build"

### Verify Installation

```bash
# Check bot status
docker logs lukas-bear-bot-dev --tail 50

# Check dashboard status
curl http://localhost:8080/api/health

# Check MCP tools loaded
docker logs lukas-bear-bot-dev | grep "MCP"
```

**Expected Output**:
```
✅ MCP server started successfully
✅ Internal API started successfully
🐻 Lukas the Bear is online and ready!
MCP initialization complete: 8 total tools from 2 server(s)
```

---

## 💡 Usage Examples

### Natural Language Commands

No need to memorize exact syntax - just ask naturally:

```
You: "Remind me in 30 minutes to check the build"
Lukas: Sure! I'll remind you in 30 minutes about "check the build" 🐻

You: "Post 'Meeting at 3pm' to #general"
Lukas: Posted your message to #general! ✓

You: "Who's on the team?"
Lukas: Here's our team roster: [lists team members]

You: "Generate an image with a celebration theme"
Lukas: Creating a celebratory bear image... done! 🎨
```

### Direct Conversations

```
You: What's the weather like in San Francisco?
Lukas: Let me search for that... [uses web search tool]
      According to current weather data, it's 68°F and partly cloudy in SF!

You: How do I center a div in CSS?
Lukas: [searches web and provides answer with code examples]
```

### Dashboard Controls

1. **Navigate to Manual Controls** (http://localhost:8080/controls)

2. **Generate Image**:
   - Theme: "celebration" (optional)
   - Channel: Leave blank for default
   - Click "Generate Image"

3. **Send Proactive DM**:
   - Select user from dropdown (or leave as "Random")
   - Click "Send DM"

4. **View Results**:
   - Check Image Gallery for generated images
   - Check Task History for execution audit log

---

## ⚙️ Configuration

### Bot Settings (`config/config.yml`)

```yaml
bot:
  name: "Lukas the Bear"
  timezone: "America/New_York"

  proactive_dm:
    enabled: true
    interval_hours: 12      # How often to send random DMs
    quiet_hours_start: 22   # Don't send DMs after 10pm
    quiet_hours_end: 8      # Don't send DMs before 8am

  image_posting:
    enabled: true
    interval_days: 7        # Weekly image generation
    channel: "#random"

  thread_participation:
    probability: 0.3        # 30% chance to join threads
    min_messages: 3         # Only join active threads

  llm:
    model: "gpt-5-mini-2025-08-07"
    max_tokens: 8000
    temperature: 0.7

  features:
    use_mcp_agent: true     # Enable MCP tools
    enable_web_search: true # Enable web search MCP
```

### Personality (`config/persona_prompts.yml`)

Customize Lukas's personality:

```yaml
persona:
  name: "Lukas the Bear"
  description: "A friendly, helpful bear who loves technology"

  tone:
    - friendly
    - professional
    - enthusiastic

  greeting_templates:
    - "Hey there! 🐻"
    - "Howdy! What can I help you with?"
```

### Environment Variables (`.env`)

**Required**:
```bash
# Slack Authentication
SLACK_BOT_TOKEN=xoxb-...        # OAuth token
SLACK_APP_TOKEN=xapp-...        # Socket Mode token

# AI Services
OPENAI_API_KEY=sk-...           # GPT + DALL-E

# Dashboard Security
DASHBOARD_SECRET_KEY=...        # Random 32-char string
DASHBOARD_ADMIN_PASSWORD=...    # Secure password
```

**Optional**:
```bash
# Feature Flags
USE_MCP_AGENT=true              # Enable MCP tools (default: true)

# LLM Configuration
LLM_MODEL=gpt-5-mini-2025-08-07 # Override model

# MCP Server URLs (auto-configured for Docker)
MCP_WEB_SEARCH_URL=http://web-search-mcp-dev:9765/sse
MCP_SLACK_OPS_URL=http://localhost:9766/sse
```

**Generate Secure Keys**:
```bash
# Dashboard secret key
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────┐
│                Docker Network                       │
│                                                     │
│  ┌────────────────────┐    ┌──────────────────┐   │
│  │  Bot Container     │    │  Dashboard       │   │
│  │  • Slack Bot       │◄───┤  • Flask API     │   │
│  │  • MCP Server      │    │  • Vue.js SPA    │   │
│  │  • Internal API    │    └──────────────────┘   │
│  │  • SQLite DB       │                            │
│  └────────────────────┘    ┌──────────────────┐   │
│          │                  │  Web Search MCP  │   │
│          └─────────────────►│  (Node.js)       │   │
│                              └──────────────────┘   │
└─────────────────────────────────────────────────────┘
            │
            ▼
    External Services
    • Slack API
    • OpenAI API
```

### Key Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Bot** | Python 3.11 + Slack Bolt | Core chatbot logic |
| **Agent** | LangChain + LangGraph | LLM agent with tools |
| **Tools** | MCP SDK | Standardized tool protocol |
| **Dashboard** | Flask + Vue.js 3 + Vite | Admin web interface |
| **Database** | SQLite + Alembic | Data persistence & migrations |
| **Scheduler** | APScheduler | Background task execution |
| **Search** | Node.js + Playwright | Web scraping capabilities |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.

---

## 🧪 Development

### Local Development Setup

```bash
# 1. Set up Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start development containers
docker-compose -f docker-compose.dev.yml up -d

# 3. View logs
docker logs lukas-bear-bot-dev -f
docker logs dashboard-dev -f

# 4. Make changes
# - Bot code: Edit src/, restart container
# - Dashboard backend: Edit dashboard/backend/, auto-reload
# - Dashboard frontend: Edit dashboard/frontend/, HMR enabled

# 5. Run tests
pytest

# 6. Check code quality
ruff check .
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test type
pytest tests/unit/         # Unit tests only
pytest tests/integration/  # Integration tests only

# Run specific test
pytest tests/unit/services/test_llm_service.py

# View coverage report
open htmlcov/index.html
```

### Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new column"

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for comprehensive developer guide.

---

## 📁 Project Structure

```
lukas_chat_bear/
├── src/                    # Bot application
│   ├── bot.py             # Main entry point
│   ├── mcp_server.py      # Slack Operations MCP server
│   ├── api/               # Internal API for dashboard
│   ├── handlers/          # Slack event handlers
│   ├── services/          # Business logic
│   ├── models/            # SQLAlchemy models
│   ├── repositories/      # Data access layer
│   └── utils/             # Shared utilities
│
├── dashboard/             # Web admin interface
│   ├── backend/          # Flask REST API
│   │   ├── routes/       # API endpoints
│   │   └── services/     # Business logic
│   └── frontend/         # Vue.js SPA
│       └── src/
│           ├── views/    # Page components
│           ├── components/ # UI components
│           └── services/ # API clients
│
├── docker/               # Docker configuration
│   ├── Dockerfile        # Bot container
│   ├── start-bot.sh      # Multi-process startup
│   └── mcp-servers/      # External MCP servers
│
├── config/               # Configuration files
│   ├── config.yml        # Bot settings
│   └── persona_prompts.yml # Personality definition
│
├── migrations/           # Database migrations (Alembic)
├── tests/                # Test suite
├── specs/                # Feature specifications
└── docs/                 # Additional documentation
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed breakdown.

---

## 🔧 Troubleshooting

### Bot Won't Start

**Symptoms**: Container exits immediately or logs show errors

**Solutions**:
1. Check environment variables:
   ```bash
   docker exec lukas-bear-bot-dev env | grep SLACK
   ```
2. Verify Slack tokens are correct
3. Ensure Socket Mode is enabled in Slack app
4. Check logs: `docker logs lukas-bear-bot-dev --tail 100`

### Bot Not Responding to Messages

**Symptoms**: Bot online but doesn't reply

**Solutions**:
1. Verify bot has required OAuth scopes
2. Ensure bot is invited to channels
3. Check handler registration in logs:
   ```bash
   docker logs lukas-bear-bot-dev | grep "handlers registered"
   ```
4. Test with direct DM (works even if channel access is wrong)

### MCP Tools Not Working

**Symptoms**: Bot replies but doesn't use tools

**Solutions**:
1. Check MCP initialization:
   ```bash
   docker logs lukas-bear-bot-dev | grep "MCP"
   ```
2. Verify `USE_MCP_AGENT=true` in environment
3. Check MCP server connectivity:
   ```bash
   docker exec lukas-bear-bot-dev curl http://localhost:9766/sse
   ```
4. Restart bot container: `docker-compose restart lukas-bot`

### Dashboard Can't Connect to Bot

**Symptoms**: Manual controls fail with "Bot unavailable"

**Solutions**:
1. Check bot internal API health:
   ```bash
   docker exec dashboard-dev curl http://lukas-bear-bot-dev:5001/api/internal/health
   ```
2. Verify Docker network: `docker network ls`
3. Check `BOT_API_URL` environment variable
4. Restart both containers:
   ```bash
   docker-compose -f docker-compose.dev.yml restart
   ```

### High API Costs

**Symptoms**: OpenAI bills higher than expected

**Solutions**:
1. Increase DM interval: Set `interval_hours: 24` in config
2. Decrease thread probability: Set `probability: 0.1` in config
3. Use cheaper model: Set `model: "gpt-3.5-turbo"` in config
4. Disable image generation: Set `enabled: false` under `image_posting`
5. Monitor usage in OpenAI dashboard

### Database Locked Errors

**Symptoms**: `database is locked` errors in logs

**Solutions**:
1. Stop all containers: `docker-compose down`
2. Restart: `docker-compose up -d`
3. **Long-term**: Migrate to PostgreSQL (see [ARCHITECTURE.md](ARCHITECTURE.md))

---

## 🔒 Security Considerations

### Secrets Management
- Never commit `.env` file
- Use strong dashboard password
- Rotate API keys regularly
- Use environment variables for all secrets

### Network Security
- Bot internal API not exposed to internet
- Dashboard should be behind reverse proxy in production
- Use HTTPS for dashboard in production
- Docker network isolation between containers

### Data Protection
- Database contains conversation history (sensitive)
- Regular backups recommended
- Consider encryption at rest for production

See [ARCHITECTURE.md - Security](ARCHITECTURE.md#security-architecture) for detailed security documentation.

---

## 🚀 Deployment

### Production Checklist

- [ ] Use `docker-compose.yml` (not dev version)
- [ ] Set strong `DASHBOARD_SECRET_KEY` and `DASHBOARD_ADMIN_PASSWORD`
- [ ] Configure reverse proxy (Nginx) with SSL for dashboard
- [ ] Set up regular database backups
- [ ] Configure log aggregation (ELK, Splunk, etc.)
- [ ] Set resource limits in docker-compose
- [ ] Enable health check monitoring
- [ ] Document disaster recovery procedure

### Database Backup

```bash
# Backup database
docker exec lukas-bear-bot-dev sqlite3 /app/data/lukas.db \
  ".backup '/app/data/backup-$(date +%Y%m%d).db'"

# Restore from backup
docker exec -it lukas-bear-bot-dev sqlite3 /app/data/lukas.db \
  ".restore '/app/data/backup-20250129.db'"

# Copy backup to host
docker cp lukas-bear-bot-dev:/app/data/backup-20250129.db ./backups/
```

### Monitoring

Key metrics to monitor:
- Bot container health (uptime, memory, CPU)
- Slack API rate limits and errors
- OpenAI API usage and costs
- MCP server availability
- Database size and performance
- Dashboard response times

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/your-feature`
3. **Make changes** with tests
4. **Run quality checks**:
   ```bash
   pytest
   ruff check .
   ```
5. **Commit with conventional message**:
   ```
   feat(dashboard): Add user targeting for DM control

   Allows selecting specific user instead of random selection.
   ```
6. **Push and create pull request**

### Commit Message Convention

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

See [DEVELOPMENT.md - Contributing](DEVELOPMENT.md#contributing) for details.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 📞 Support

### Documentation
- [Development Guide](DEVELOPMENT.md) - Setup and workflow
- [Architecture Overview](ARCHITECTURE.md) - System design
- [API Documentation](docs/API.md) - API reference
- [Project Structure](PROJECT_STRUCTURE.md) - Code organization

### Getting Help
- Check documentation above
- Search existing issues
- Create new issue with details:
  - Environment (OS, Docker version)
  - Steps to reproduce
  - Expected vs actual behavior
  - Relevant logs

### Community
- GitHub Issues: Bug reports and feature requests
- GitHub Discussions: Questions and ideas

---

**Built with** ❤️ **and** 🐻 **for your team**

**Version**: 1.0.0
**Last Updated**: 2025-10-29
