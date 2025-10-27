# Lukas the Bear - Slack Chatbot 🐻

A friendly AI-powered Slack chatbot that embodies your team's beloved bear mascot, "Lukas the Bear."

## Features

- **Direct Conversations**: Team members can chat with Lukas via DM for friendly, contextual conversations
- **Proactive Engagement**: Lukas randomly reaches out to team members and participates in channel discussions
- **AI-Generated Images**: Periodic posting of whimsical bear-themed artwork to boost team morale
- **Utility Commands**: Execute helpful commands like posting messages, setting reminders, and more
- **Personality-Driven**: Maintains a warm, encouraging bear persona across all interactions

## Quick Start

### Prerequisites

- Docker & Docker Compose (v2.0+)
- Slack workspace with admin access
- LLM provider API key (OpenAI, Anthropic, or local Ollama)
- OpenAI API key (for DALL-E image generation)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd lukas_chat_bear
   git checkout 001-lukas-bear-chatbot
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and tokens
   ```

3. **Configure bot settings**:
   ```bash
   cp config/config.example.yml config/config.yml
   # Customize intervals, probabilities, and persona
   ```

4. **Create Slack app** (see [Quickstart Guide](specs/001-lukas-bear-chatbot/quickstart.md) for detailed steps):
   - Create app at https://api.slack.com/apps
   - Add required OAuth scopes
   - Enable Socket Mode
   - Install to workspace

5. **Run with Docker Compose**:
   ```bash
   docker compose up --build -d
   ```

6. **View logs**:
   ```bash
   docker compose logs -f lukas-bot
   ```

## Documentation

- **[Quickstart Guide](specs/001-lukas-bear-chatbot/quickstart.md)**: Detailed setup instructions
- **[Technical Plan](specs/001-lukas-bear-chatbot/plan.md)**: Architecture and design decisions
- **[Data Model](specs/001-lukas-bear-chatbot/data-model.md)**: Database schema
- **[API Contracts](specs/001-lukas-bear-chatbot/contracts/)**: Slack and LLM integration specs
- **[Research Decisions](specs/001-lukas-bear-chatbot/research.md)**: Technology choices and trade-offs

## Usage Examples

### Direct Message
```
You: Hi Lukas, how are you?
Lukas: Hey there! I'm doing great, thanks for asking! 🐻 How's your day going?
```

### Admin Command
```
You: @Lukas set random DM interval to 2 hours
Lukas: Got it! I'll now send random DMs every 2 hours. 🐻
```

### Channel Mention
```
You: @Lukas what do you think about this idea?
Lukas: That sounds interesting! I think there's a lot of potential there...
```

## Configuration

### Key Settings (`config/config.yml`)

- **`random_dm_interval_hours`**: How often Lukas sends proactive DMs (default: 24)
- **`thread_response_probability`**: Chance Lukas responds to threads (default: 0.20 = 20%)
- **`image_post_interval_days`**: How often images are posted (default: 7)
- **`active_hours`**: When Lukas is active (default: 8am-6pm)

### Environment Variables (`.env`)

- **`SLACK_BOT_TOKEN`**: Bot OAuth token (starts with `xoxb-`)
- **`SLACK_APP_TOKEN`**: App-level token for Socket Mode (starts with `xapp-`)
- **`LLM_PROVIDER`**: LLM provider (`openai`, `anthropic`, `ollama`, etc.)
- **`LLM_MODEL`**: Model name (e.g., `gpt-3.5-turbo`)
- **`OPENAI_API_KEY`**: OpenAI API key (for LLM and/or DALL-E)

## Development

### Local Setup (without Docker)

1. **Install dependencies with uv**:
   ```bash
   # Install uv package manager
   pip install uv

   # Sync dependencies
   uv sync --dev
   ```

2. **Run database migrations**:
   ```bash
   uv run alembic upgrade head
   ```

3. **Start the bot**:
   ```bash
   uv run python -m src.bot
   ```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Run specific test file
uv run pytest tests/unit/test_persona_service.py
```

### Code Quality

```bash
# Run linter
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Type checking
uv run mypy src/
```

## Project Structure

```
lukas_chat_bear/
├── src/
│   ├── handlers/          # Slack event handlers
│   ├── services/          # Business logic
│   ├── models/            # SQLAlchemy models
│   ├── repositories/      # Data access layer
│   └── utils/             # Shared utilities
├── tests/
│   ├── integration/       # Integration tests
│   ├── unit/              # Unit tests
│   └── fixtures/          # Test data
├── config/                # Configuration files
├── docker/                # Docker build files
├── migrations/            # Database migrations
├── data/                  # SQLite database (created at runtime)
└── specs/                 # Design documentation

```

## Troubleshooting

### Bot won't start
- Check `.env` file has correct Slack tokens
- Verify Socket Mode is enabled in Slack app
- Review logs: `docker compose logs lukas-bot`

### Bot not responding
- Ensure bot is online in Slack (green dot)
- Check OAuth scopes are correct
- Verify bot is invited to channels

### High API costs
- Increase `random_dm_interval_hours`
- Decrease `thread_response_probability`
- Switch to cheaper LLM model or use local Ollama

See [Quickstart Guide](specs/001-lukas-bear-chatbot/quickstart.md#part-8-troubleshooting) for detailed troubleshooting.

## Maintenance

### Updating Dependencies
```bash
uv sync --upgrade
docker compose up --build -d
```

### Database Backup
```bash
docker compose exec lukas-bot sqlite3 /app/data/lukas.db ".backup '/app/data/backup-$(date +%Y%m%d).db'"
```

### Viewing Logs
```bash
docker compose logs --tail=100 lukas-bot
```

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests: `uv run pytest`
4. Run linter: `uv run ruff check .`
5. Submit pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check [Quickstart Guide](specs/001-lukas-bear-chatbot/quickstart.md)
- Review [Technical Documentation](specs/001-lukas-bear-chatbot/)
- Open an issue in the repository

---

**Built with** ❤️ **and** 🐻 **for your research team**
