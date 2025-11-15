#!/bin/sh
# Development startup script for dashboard
# Runs both Flask backend and Vite frontend dev server

set -e

echo "🚀 Starting Dashboard Development Servers..."

# Start Vite dev server in the background
echo "📦 Starting Vite dev server on port 5173..."
cd /app/frontend
npm run dev -- --host 0.0.0.0 &
VITE_PID=$!

# Give Vite a moment to start
sleep 2

# Start Flask backend
echo "🐍 Starting Flask backend on port 8080..."
cd /app/backend
python -m flask run --host=0.0.0.0 --port=8080 --debug &
FLASK_PID=$!

echo "✅ Dashboard dev servers started!"
echo "   - Backend: http://localhost:8080"
echo "   - Frontend: http://localhost:5173"

# Wait for both processes
wait $VITE_PID $FLASK_PID
