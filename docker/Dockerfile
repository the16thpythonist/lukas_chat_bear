# Lukas the Bear Chatbot Dockerfile
# Python 3.11 base image

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager, which is the preferred solution 
# in the modern python ecosystem.
RUN pip install --no-cache-dir uv

# Copy dependency files. These are all the files which need to 
# be present in the root directory of the container for the code 
# to run.
COPY pyproject.toml ./
COPY README.md ./
COPY alembic.ini ./

# Install Python dependencies using uv
RUN uv pip install --system --no-cache -e .

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY migrations/ ./migrations/

# Create data directory
# This is where the SQLite database file will be stored, 
# for instance.
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose no ports (uses Slack Socket Mode - no incoming connections needed)

# Copy startup scripts
# entrypoint.sh: Runs migrations
# start-bot.sh: Starts both MCP server and Slack bot
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/start-bot.sh /start-bot.sh
RUN chmod +x /entrypoint.sh /start-bot.sh

# Set entrypoint to run migrations then start both processes
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start-bot.sh"]
