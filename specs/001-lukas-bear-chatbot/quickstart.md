# Quickstart Guide: Lukas the Bear Slack Chatbot

**Last Updated**: 2025-10-24
**Target Audience**: Developers and Administrators

This guide walks you through setting up and running Lukas the Bear chatbot from scratch.

---

## Prerequisites

**Required**:
- Docker & Docker Compose (v2.0+)
- Python 3.11+ and `uv` package manager
- Slack workspace admin access
- LLM provider API key (OpenAI, Anthropic, Mistral, or local ollama)
- OpenAI API account (for DALL-E image generation)

**Knowledge Assumed**:
- Basic Docker operations
- Slack app creation
- YAML configuration editing
- Basic Python virtual environments

**Estimated Setup Time**: 30-45 minutes

---

## Part 1: Slack App Setup

### 1.1 Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. App Name: "Lukas the Bear"
4. Select your workspace
5. Click "Create App"

### 1.2 Configure OAuth Scopes

Navigate to "OAuth & Permissions" in sidebar:

**Bot Token Scopes** (add all of these):
- `channels:history` - Read general channel messages
- `channels:read` - List workspace channels
- `chat:write` - Post messages
- `im:history` - Read direct messages
- `im:write` - Send direct messages
- `users:read` - Access team member profiles
- `files:write` - Upload generated images
- `reactions:write` - Add emoji reactions to messages
- `app_mentions:read` - Receive @mentions

Click "Install to Workspace" → "Allow"

**Save this token**: Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### 1.3 Enable Socket Mode

1. Navigate to "Socket Mode" in sidebar
2. Toggle "Enable Socket Mode" → ON
3. Create an app-level token:
   - Token Name: "lukas-socket-token"
   - Scope: `connections:write`
   - Click "Generate"
4. **Save this token**: Copy the token (starts with `xapp-`)

### 1.4 Subscribe to Events

Navigate to "Event Subscriptions":

1. Toggle "Enable Events" → ON
2. **Don't add a Request URL** (Socket Mode doesn't need it)
3. Under "Subscribe to bot events", add:
   - `message.im` - Direct messages
   - `message.channels` - Channel messages
   - `app_mention` - When @mentioned
4. Click "Save Changes"

### 1.5 Set Display Information

Navigate to "Basic Information":

1. **App Icon**: Upload a bear image (optional)
2. **Short Description**: "Lukas the Bear - Your friendly research team mascot"
3. **Background Color**: #D2691E (bear brown color)
4. Click "Save Changes"

---

## Part 2: LLM Provider Setup

### 2.1 Choose Your LLM Provider

The bot uses `any-llm` (Mozilla AI) which supports multiple providers. Choose one:

**Option A: OpenAI** (recommended for beginners)
- Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Create new API key
- **Save key**: Starts with `sk-`
- **Model**: `gpt-3.5-turbo` (cost-effective) or `gpt-4` (higher quality)

**Option B: Anthropic Claude**
- Go to [https://console.anthropic.com/](https://console.anthropic.com/)
- Create API key
- **Save key**: Starts with `sk-ant-`
- **Model**: `claude-3-haiku` (fast, cheap) or `claude-3-sonnet` (balanced)

**Option C: Local Models (Free)**
- Install ollama: [https://ollama.ai](https://ollama.ai)
- Pull a model: `ollama pull llama2`
- **No API key needed**
- **Model**: `llama2`, `mistral`, etc.

**Option D: Other Providers**
- Mistral AI, Cohere, HuggingFace - any-llm supports many providers

### 2.2 Note Your Configuration

You'll need:
- **Provider name**: `openai`, `anthropic`, `ollama`, etc.
- **Model name**: Provider-specific (e.g., `gpt-3.5-turbo`)
- **API key**: (if not using local ollama)

---

## Part 3: OpenAI API Setup

### 3.1 Get DALL-E API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create new secret key
3. **Save this key**: Copy the key (starts with `sk-`)

### 3.2 Set Usage Limits (Recommended)

1. Navigate to Usage Limits
2. Set monthly budget (e.g., $10/month)
3. Enable email alerts at 75% usage

**Cost Estimate**:
- DALL-E (1 image/week): ~$0.17/month
- LLM API costs (varies by provider - OpenAI/Anthropic/etc or free with ollama)

---

## Part 4: Local Development Setup

### 4.1 Install uv Package Manager

If you don't have `uv` installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Or with Homebrew (macOS)
brew install uv
```

Verify installation:
```bash
uv --version
```

### 4.2 Clone Repository

```bash
git clone <repository-url>
cd lukas_chat_bear
git checkout 001-lukas-bear-chatbot
```

### 4.3 Install Dependencies

```bash
# Create virtual environment and install all dependencies
uv sync

# This creates .venv/ and installs from pyproject.toml
# For development dependencies too:
uv sync --dev
```

**What `uv sync` does:**
- Creates Python 3.11+ virtual environment
- Installs all dependencies from `pyproject.toml`
- Generates/updates `uv.lock` file for reproducible installs
- Much faster than pip (Rust-based package manager)

### 4.4 Create Environment File

Create `.env` file in project root:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-level-token-here

# LLM Provider Configuration (choose one or more)
LLM_PROVIDER=openai  # or anthropic, ollama, mistral, cohere, etc.
LLM_MODEL=gpt-3.5-turbo  # Provider-specific model name

# Provider API Keys (set the one matching your LLM_PROVIDER)
OPENAI_API_KEY=sk-your-openai-key-here  # If using openai
# ANTHROPIC_API_KEY=sk-ant-your-key-here  # If using anthropic
# MISTRAL_API_KEY=your-mistral-key-here   # If using mistral
# (ollama requires no API key)

# OpenAI Configuration (for DALL-E image generation - required)
OPENAI_API_KEY=sk-your-openai-key-here

# Database Configuration (optional override)
DATABASE_URL=sqlite:///data/lukas.db

# Logging Level
LOG_LEVEL=INFO
```

**Security**: Add `.env` to `.gitignore` to prevent committing secrets!

### 4.5 Create Configuration File

Copy example config and customize:

```bash
cp config/config.example.yml config/config.yml
```

Edit `config/config.yml`:

```yaml
bot:
  persona:
    name: "Lukas the Bear"
    personality_file: "persona_prompts.yml"

  engagement:
    random_dm_interval_hours: 24  # How often to send proactive DMs
    thread_response_probability: 0.20  # 20% chance to engage in threads
    active_hours:
      start: "08:00"  # Bot active from 8am...
      end: "18:00"    # ...to 6pm
      timezone: "America/New_York"  # Adjust to your team's timezone

  image_posting:
    interval_days: 7  # Post image once per week
    channel: "#random"  # Where to post images

  llm:
    provider: "openai"  # From LLM_PROVIDER env var
    model: "gpt-3.5-turbo"  # From LLM_MODEL env var
    max_context_messages: 10  # Last 10 message pairs
    max_tokens_per_request: 4000

  database:
    conversation_retention_days: 90  # Keep conversations for 90 days

  admin_users:  # Slack user IDs who can use admin commands
    - "U123ABC456"  # Add your Slack user ID here
```

**Finding Your Slack User ID**:
1. Click your profile in Slack
2. Click "More" → "Copy member ID"
3. Add to `admin_users` list

### 4.6 Create Data Directory

```bash
mkdir -p data
```

---

## Part 5: Running with Docker Compose

### 5.1 Build and Start

**Note**: `docker-compose.yml` is at the project root for convenient access.

```bash
# From project root
docker compose up --build -d
```

This will:
- Build the Python application image
- Start the bot service
- Create SQLite database in `data/` directory
- Run database migrations

### 5.2 View Logs

```bash
# Follow logs in real-time
docker compose logs -f lukas-bot

# View last 100 lines
docker compose logs --tail=100 lukas-bot
```

**Expected Startup Logs**:
```
[INFO] Starting Lukas the Bear chatbot...
[INFO] Running database migrations...
[INFO] Connecting to Slack via Socket Mode...
[INFO] Connected to workspace: YourWorkspace
[INFO] Scheduling proactive DM task (interval: 24 hours)
[INFO] Scheduling image posting task (interval: 7 days)
[INFO] Bot is ready! 🐻
```

### 5.3 Verify Bot is Online

In Slack:
1. Go to "Apps" in sidebar
2. Find "Lukas the Bear"
3. Status should show green dot (online)

---

## Part 6: Testing the Bot

### 6.1 Test Direct Messages

1. Open DM with Lukas the Bear
2. Send: "Hi Lukas!"
3. Expect response within 5 seconds with bear persona

**Example**:
```
You: Hi Lukas!
Lukas: Hey there! Good to hear from you! 🐻 How can I help you today?
```

### 6.2 Test Channel Mention

1. Invite Lukas to a channel: `/invite @Lukas the Bear`
2. Post: "@Lukas the Bear what's the weather?"
3. Expect response in thread

### 6.3 Test Proactive Features (Wait)

**Random DM**: Wait configured interval (default 24 hours) to receive proactive message

**Thread Engagement**: Post in general channel and watch for Lukas to occasionally respond

**Image Posting**: Wait configured interval (default 7 days) to see image post

### 6.4 Test Admin Commands

As admin user, DM Lukas:

```
set random DM interval to 2 hours
```

Expected response:
```
Got it! I'll now send random DMs every 2 hours. 🐻
```

---

## Part 7: Production Deployment

### 7.1 Environment-Specific Configuration

**Production `.env`**:
- Use production API keys
- Set `LOG_LEVEL=WARNING` (less verbose)
- Consider using managed secrets (AWS Secrets Manager, etc.)

### 7.2 Persistent Data

Ensure `data/` directory is backed up:

```yaml
# docker-compose.yml
services:
  lukas-bot:
    volumes:
      - ./data:/app/data  # Persists database across restarts
```

**Backup Strategy**:
```bash
# Backup database daily
docker compose exec lukas-bot \
  sqlite3 /app/data/lukas.db ".backup '/app/data/backup-$(date +%Y%m%d).db'"
```

### 7.3 Monitoring

**Health Check**:
```bash
# Check if container is running
docker compose ps

# Check logs for errors
docker compose logs --tail=50 lukas-bot | grep ERROR
```

**Metrics to Monitor**:
- Bot uptime (should be >99% during business hours)
- API error rate (should be <1%)
- Response time (should be <5s p95)
- Daily message count (track engagement trends)

### 7.4 Restart After Configuration Changes

```bash
# After editing config.yml or .env
docker compose restart lukas-bot
```

**Note**: Some config changes apply immediately, others need restart.

---

## Part 8: Troubleshooting

### Bot Won't Start

**Check logs**:
```bash
docker compose logs lukas-bot
```

**Common Issues**:

1. **"Invalid Slack token"**
   - Verify `SLACK_BOT_TOKEN` in `.env`
   - Ensure token starts with `xoxb-`
   - Reinstall app to workspace if needed

2. **"Socket Mode connection failed"**
   - Verify `SLACK_APP_TOKEN` in `.env`
   - Ensure Socket Mode enabled in Slack app settings
   - Check token starts with `xapp-`

3. **"Database migration failed"**
   - Check `data/` directory exists and is writable
   - Delete `data/lukas.db` and restart (loses data!)

4. **"LLM API error"**
   - Verify `LLM_PROVIDER` is correct (openai, anthropic, etc.)
   - Check corresponding API key is set (OPENAI_API_KEY, etc.)
   - Verify model name is valid for your provider

### Bot Not Responding to Messages

**Check**:
1. Bot shows as online in Slack (green dot)
2. Bot has required OAuth scopes
3. Bot is invited to channel (for channel messages)
4. Check logs for errors during message handling

**Test Connection**:
```bash
# Check if bot can post to test channel
docker compose exec lukas-bot python -c "
from slack_sdk import WebClient
client = WebClient(token='$SLACK_BOT_TOKEN')
response = client.chat_postMessage(channel='#test', text='Test message')
print(response)
"
```

### Bot Responds But Persona is Wrong

**Check**:
1. `config/persona_prompts.yml` contains system prompt
2. LLM provider and model configured correctly in `.env`
3. Conversation context loading correctly (check logs)

**Reset Conversation**:
Delete conversation session from database to start fresh:
```bash
docker compose exec lukas-bot python -c "
from src.models import ConversationSession
from src.database import session
# Find and delete conversation
"
```

### Proactive Features Not Working

**Random DMs Not Sending**:
1. Check `random_dm_interval_hours` in config
2. Verify APScheduler logs show scheduled jobs
3. Check no users have `is_bot=TRUE` (filters them out)

**Thread Engagement Not Happening**:
1. Verify `thread_response_probability` > 0
2. Check bot is in channel where threads occur
3. Review `EngagementEvent` table for decision logs

**Images Not Posting**:
1. Check `OPENAI_API_KEY` is valid
2. Verify `interval_days` in config
3. Review `GeneratedImage` table for errors
4. Check bot has `files:write` permission

### High API Costs

**Reduce Costs**:
1. Increase `random_dm_interval_hours` (fewer DMs)
2. Decrease `thread_response_probability` (less engagement)
3. Increase `image_posting.interval_days` (fewer images)
4. Switch to cheaper model (gpt-3.5-turbo instead of gpt-4, or use ollama for free)
5. Reduce `max_context_messages` (fewer tokens per request)

**Monitor Costs**:
- OpenAI dashboard: [https://platform.openai.com/usage](https://platform.openai.com/usage)
- Anthropic dashboard: [https://console.anthropic.com/](https://console.anthropic.com/)
- Other provider dashboards (check your provider's website)

---

## Part 9: Customization

### 9.1 Customize Persona

Edit `config/persona_prompts.yml`:

```yaml
system_prompt: |
  You are Lukas the Bear, a stuffed animal and beloved mascot of a research team.

  [Edit personality traits, tone, guidelines here]

fallback_responses:
  - "I'm feeling a bit fuzzy right now 🐻 Can you try again in a moment?"
  - [Add more fallback responses here]

greeting_templates:
  - "Hey! Just checking in - how's your week going? 🐻"
  - [Add more greeting templates for random DMs]
```

**Apply Changes**: Restart bot
```bash
docker compose restart lukas-bot
```

### 9.2 Adjust Engagement Levels

Edit `config/config.yml`:

```yaml
engagement:
  random_dm_interval_hours: 48  # Less frequent DMs
  thread_response_probability: 0.10  # More selective engagement
```

### 9.3 Change Image Themes

Edit `src/services/image_service.py` prompt templates (requires code change):
- Add seasonal themes
- Customize art style
- Add team-specific references

### 9.4 Add Custom Commands

Extend `src/handlers/command_handler.py`:
- Define new command patterns
- Implement command logic
- Update help text

---

## Part 10: Maintenance

### 10.1 Updating Dependencies

**With uv**:
```bash
# Update all dependencies to latest compatible versions
uv sync --upgrade

# Update specific package
uv add slack-bolt@latest

# Add new dependency
uv add <package-name>

# Add dev dependency
uv add --dev pytest-timeout
```

**After updating**:
- Review `uv.lock` changes
- Run tests: `uv run pytest`
- Rebuild Docker image if deploying

### 10.2 Version Management and CHANGELOG

**When releasing a new version**:

1. **Update CHANGELOG.md**:
   ```markdown
   ## [0.2.0] - 2025-11-15

   ### Added
   - New feature X

   ### Fixed
   - Bug Y in module Z
   ```

2. **Update version in pyproject.toml**:
   ```toml
   [project]
   version = "0.2.0"
   ```

3. **Commit and tag**:
   ```bash
   git add CHANGELOG.md pyproject.toml
   git commit -m "chore: release v0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```

**CHANGELOG best practices**:
- Keep `[Unreleased]` section for work in progress
- Use categories: Added, Changed, Deprecated, Removed, Fixed, Security
- Move `[Unreleased]` items to versioned section on release
- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Link to semantic versioning for version number guidance

### 10.3 Database Cleanup

Automatic cleanup runs daily at 2am (configured timezone):
- Deletes conversations older than retention period
- Archives completed scheduled tasks
- Cleans up old engagement events

**Manual Cleanup**:
```bash
docker compose exec lukas-bot python -m src.maintenance.cleanup
```

### 10.4 Backup Database

**Manual Backup**:
```bash
docker compose exec lukas-bot \
  cp /app/data/lukas.db /app/data/backup-$(date +%Y%m%d).db
```

**Automated Backup** (add to host cron):
```bash
# Daily at 3am
0 3 * * * cd /path/to/lukas_chat_bear && docker compose exec -T lukas-bot sqlite3 /app/data/lukas.db ".backup '/app/data/backup-$(date +\%Y\%m\%d).db'"
```

### 10.5 Update Bot

```bash
# Pull latest code
git pull origin 001-lukas-bear-chatbot

# Update dependencies (if pyproject.toml changed)
uv sync

# Rebuild and restart
docker compose up --build -d

# Check logs for errors
docker compose logs -f lukas-bot
```

### 10.6 Monitor Logs

**Error Monitoring**:
```bash
# Watch for errors
docker compose logs -f lukas-bot | grep ERROR

# Count errors in last hour
docker compose logs --since=1h lukas-bot | grep ERROR | wc -l
```

**Disk Usage**:
```bash
# Check database size
du -h data/lukas.db

# Check Docker volumes
docker system df
```

---

## Part 11: Next Steps

**After Successful Setup**:

1. **Gather Feedback**: Ask team about Lukas's personality and engagement levels
2. **Tune Parameters**: Adjust intervals and probabilities based on team preferences
3. **Monitor Engagement**: Review `EngagementEvent` and `ConversationSession` tables for usage patterns
4. **Plan Enhancements**: Consider Phase 2 features (polls, reminders, calendar integration)

**Support Resources**:
- Documentation: `specs/001-lukas-bear-chatbot/`
- Issue Tracker: [Project repository issues]
- Slack: #lukas-bear-dev (if you have a dev channel)

---

## Appendix A: Configuration Reference

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SLACK_BOT_TOKEN` | Yes | Bot OAuth token | `xoxb-1234...` |
| `SLACK_APP_TOKEN` | Yes | App-level token | `xapp-1-AAA...` |
| `LLM_PROVIDER` | Yes | LLM provider name | `openai`, `anthropic`, `ollama` |
| `LLM_MODEL` | Yes | Provider-specific model | `gpt-3.5-turbo`, `claude-3-haiku` |
| `OPENAI_API_KEY` | Conditional | OpenAI key (if using openai provider or DALL-E) | `sk-proj...` |
| `ANTHROPIC_API_KEY` | Conditional | Anthropic key (if using anthropic provider) | `sk-ant...` |
| `MISTRAL_API_KEY` | Conditional | Mistral key (if using mistral provider) | `mst...` |
| `DATABASE_URL` | No | Database connection | `sqlite:///data/lukas.db` |
| `LOG_LEVEL` | No | Logging verbosity | `INFO`, `WARNING`, `DEBUG` |

### Configuration File (`config/config.yml`)

See example in Part 4.5 above.

---

## Appendix B: Docker Compose Reference

**File**: `docker-compose.yml` (project root)

```yaml
services:
  lukas-bot:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: lukas-bear-bot
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./config:/app/config:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Benefits of root-level docker-compose.yml**:
- Simpler commands: `docker compose up` (no path needed)
- Standard Docker Compose convention
- Easier CI/CD integration

---

## Appendix C: Python Project Configuration (pyproject.toml)

**File**: `pyproject.toml` (project root)

**Key sections**:

```toml
[project]
name = "lukas-bear-chatbot"
version = "0.1.0"  # Update with each release
dependencies = [
    "slack-bolt>=1.18.0",
    "any-llm-sdk[openai]>=0.1.0",
    # ... other dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "ruff>=0.1.0",
    # ... dev tools
]

[tool.ruff]
line-length = 100
select = ["E", "W", "F", "I", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Common uv commands**:
```bash
# Install/sync dependencies
uv sync                    # Production deps only
uv sync --dev              # Include dev dependencies

# Add new dependency
uv add <package>           # Production
uv add --dev <package>     # Development

# Update dependencies
uv sync --upgrade          # Update all
uv add <package>@latest    # Update specific

# Run commands in venv
uv run python src/bot.py   # Run script
uv run pytest              # Run tests
uv run ruff check .        # Run linter
```

**Benefits of uv**:
- 10-100x faster than pip
- Deterministic installs via `uv.lock`
- Compatible with pip/pyproject.toml standards
- Built-in virtual environment management
- Rust-based, highly reliable

---

## Appendix D: Slack User ID Lookup

**Method 1: Slack UI**
1. Click user's profile picture
2. Click "More" → "Copy member ID"

**Method 2: API Call**
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/users.list" | jq '.members[] | select(.real_name == "Your Name") | .id'
```

**Method 3: Bot Command**
DM Lukas: "what's my user ID?"
(Requires implementing this command)

---

**End of Quickstart Guide**

For detailed architecture and design decisions, see:
- `research.md` - Technology decisions
- `data-model.md` - Database schema
- `contracts/` - API specifications
