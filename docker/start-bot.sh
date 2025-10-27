#!/bin/bash
# Startup script for Lukas Bear Bot with dual-process architecture
#
# Starts two processes in the same container:
# 1. MCP Server (slack-operations) on port 9766
# 2. Slack Bot (main application) on Socket Mode
#
# Both processes share the same codebase, database, and Slack client.

set -e  # Exit on any error

echo "=========================================="
echo "🐻 Lukas the Bear Bot - Startup"
echo "=========================================="

# Start MCP server in background
echo ""
echo "🚀 Starting MCP Server (slack-operations)..."
echo "   Port: ${MCP_SLACK_OPS_PORT:-9766}"
echo "   Endpoint: http://localhost:${MCP_SLACK_OPS_PORT:-9766}/sse"

python -m src.mcp_server &
MCP_PID=$!

echo "   Process ID: $MCP_PID"

# Give MCP server time to initialize
echo "   Waiting for MCP server to start..."
sleep 3

# Check if MCP server is still running
if ! kill -0 $MCP_PID 2>/dev/null; then
    echo "❌ ERROR: MCP server failed to start"
    echo "   Check logs above for errors"
    exit 1
fi

echo "✅ MCP server started successfully"

# Start Slack bot in foreground
echo ""
echo "🤖 Starting Slack Bot..."
echo "   Mode: Socket Mode (no incoming ports needed)"

# Run bot in foreground (this will block)
python -m src.bot

# Cleanup: If bot exits, kill MCP server
echo ""
echo "🛑 Slack bot stopped, cleaning up..."
kill $MCP_PID 2>/dev/null || true
echo "✅ Cleanup complete"
