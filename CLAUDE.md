# lukas_chat_bear Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-24

## Active Technologies

- Python 3.11+ + Slack Bolt SDK (Socket Mode), any-llm (Mozilla AI unified LLM interface), OpenAI SDK (for DALL-E), APScheduler, SQLAlchemy, tenacity (retry), pybreaker (circuit breaker) (001-lukas-bear-chatbot)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes

- 001-lukas-bear-chatbot: Added Python 3.11+ + Slack Bolt SDK (Socket Mode), any-llm (Mozilla AI unified LLM interface), OpenAI SDK (for DALL-E), APScheduler, SQLAlchemy, tenacity (retry), pybreaker (circuit breaker)

<!-- MANUAL ADDITIONS START -->

## Environment Setup

Before running any commands, activate the virtual environment:

```bash
source .venv/bin/activate
```

## Issue Resolution

When encountering issues or errors:

1. First, attempt to resolve the issue yourself by analyzing error messages, checking logs, and reviewing relevant code
2. If the issue persists or is unclear, use Web Search to look online for possible solutions, error explanations, and best practices
3. Search for specific error messages, stack traces, or problem descriptions to find relevant discussions and solutions

## Docker Development

**IMPORTANT:** For debugging and development, ALWAYS use the dev containers only:

```bash
# Start dev containers
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker logs lukas-bear-bot-dev -f

# Stop dev containers
docker-compose -f docker-compose.dev.yml down
```

**Do NOT use both docker-compose.yml and docker-compose.dev.yml together** unless explicitly deploying production.

<!-- MANUAL ADDITIONS END -->