#!/bin/bash
# Docker entrypoint script for Lukas the Bear chatbot
# Runs database migrations before starting the bot

set -e

echo "🐻 Lukas the Bear - Starting up..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Check if migrations succeeded
if [ $? -eq 0 ]; then
    echo "✓ Database migrations completed successfully"
else
    echo "✗ Database migrations failed"
    exit 1
fi

# Execute the main command (passed as arguments to this script)
echo "Starting bot application..."
exec "$@"
