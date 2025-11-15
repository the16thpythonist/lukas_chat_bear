# Quickstart Guide: Admin Web Dashboard

**Feature**: 002-web-dashboard
**Last Updated**: 2025-10-28

## Overview

This guide will help you set up and run the admin web dashboard for Lukas the Bear bot in both development and production environments.

---

## Prerequisites

### Required
- Docker and Docker Compose installed
- Git repository cloned
- Bot already running (generates data to view in dashboard)

### Environment Variables
Create or update `.env` file in repository root:

```bash
# Dashboard Authentication
DASHBOARD_ADMIN_PASSWORD=your-secure-password-here

# Bot Configuration (existing)
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENAI_API_KEY=sk-...
# ... other bot variables
```

**Security Note**: Use a strong password (minimum 12 characters, mix of letters, numbers, symbols)

---

## Development Setup

### Option 1: Docker Compose (Recommended)

**Start all services** (bot + web-search-mcp + dashboard):

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker logs dashboard-dev -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

**Access**:
- Dashboard: http://localhost:8080
- Login with password from `DASHBOARD_ADMIN_PASSWORD`

**Advantages**:
- Full environment with all services
- Database shared with bot (real data)
- Hot reload for frontend (HMR)
- Backend auto-reload on code changes

---

### Option 2: Local Development (Advanced)

**Backend** (terminal 1):

```bash
# Install Python dependencies
cd dashboard/backend
pip install -r requirements.txt

# Set environment variables
export DASHBOARD_ADMIN_PASSWORD=your-password
export DATABASE_PATH=../../data/bot.db  # Path to bot database

# Run Flask dev server
flask run --debug --port 5000
```

**Frontend** (terminal 2):

```bash
# Install Node dependencies
cd dashboard/frontend
npm install

# Start Vite dev server
npm run dev
# Accessible at http://localhost:5173
```

**Configure frontend to use local backend**:

Edit `dashboard/frontend/.env.development`:
```bash
VITE_API_BASE_URL=http://localhost:5000/api
```

**Advantages**:
- Fastest hot reload
- Easier debugging
- No Docker overhead

**Disadvantages**:
- Manual setup required
- Must ensure bot is running to populate database
- Need to manage multiple processes

---

## Production Deployment

### Build and Run

```bash
# Build all containers
docker-compose build

# Start production services
docker-compose up -d

# View logs
docker logs lukas-dashboard -f

# Stop services
docker-compose down
```

**Access**:
- Dashboard: http://localhost:8080
- Or configure reverse proxy (nginx/Caddy) for HTTPS

---

### Production Configuration

#### docker-compose.yml

```yaml
services:
  dashboard:
    build:
      context: .
      dockerfile: dashboard/Dockerfile.dashboard
    container_name: lukas-dashboard
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DASHBOARD_ADMIN_PASSWORD=${DASHBOARD_ADMIN_PASSWORD}
      - DATABASE_PATH=/app/data/bot.db
      - FLASK_ENV=production
    volumes:
      - ./data:/app/data:ro           # Read-only database access
      - dashboard-sessions:/app/sessions  # Session persistence
      - dashboard-thumbnails:/app/thumbnails  # Thumbnail cache
    networks:
      - lukas-network
    depends_on:
      - bot

volumes:
  dashboard-sessions:
  dashboard-thumbnails:

networks:
  lukas-network:
    driver: bridge
```

**Key Points**:
- Database mounted read-only (`:ro`) - dashboard only reads data
- Separate volumes for sessions and thumbnails (persist across restarts)
- Depends on bot service (ensures database exists)

---

### Reverse Proxy (Optional)

**nginx Configuration**:

```nginx
server {
    listen 80;
    server_name dashboard.example.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Session cookie forwarding
        proxy_cookie_path / /;
    }
}
```

**Caddy Configuration**:

```caddy
dashboard.example.com {
    reverse_proxy localhost:8080
}
```

---

## First Run

### 1. Start Services

```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Verify Services

```bash
# Check dashboard is running
docker ps | grep dashboard

# Check logs for errors
docker logs dashboard-dev
```

### 3. Access Dashboard

Open browser: http://localhost:8080

**Login Screen**:
- Enter password from `DASHBOARD_ADMIN_PASSWORD`
- Click "Login"

**Expected Behavior**:
- Redirected to Activity Log tab
- See recent bot messages (if bot has sent any)
- Tabs: Activity Log, Images, Events, Controls

### 4. Test Functionality

**Activity Log**:
- Should show bot messages
- Try filtering by date range
- Click message to see details

**Images**:
- View generated images (if bot has created any)
- Click image for full details
- Check error messages for failed generations

**Events**:
- View upcoming scheduled tasks
- View completed task history

**Manual Controls**:
- Try "Generate Image" (optional theme)
- Try "Send Random DM" (select user or random)
- Verify action completes and appears in activity log

---

## Troubleshooting

### Dashboard won't start

**Check environment variables**:
```bash
docker exec dashboard-dev env | grep DASHBOARD
```

**Check database exists**:
```bash
docker exec dashboard-dev ls -la /app/data/bot.db
```

**Check logs**:
```bash
docker logs dashboard-dev --tail 50
```

**Common Issues**:
- `DASHBOARD_ADMIN_PASSWORD` not set → Add to `.env`
- Database not found → Ensure bot container has created database
- Port 8080 already in use → Change port in docker-compose

---

### Can't log in

**Verify password**:
```bash
echo $DASHBOARD_ADMIN_PASSWORD
```

**Check session directory**:
```bash
docker exec dashboard-dev ls -la /app/sessions
```

**Clear sessions** (if stuck):
```bash
docker exec dashboard-dev rm -rf /app/sessions/*
```

---

### Activity log empty

**Possible causes**:
- Bot hasn't sent messages yet → Wait for bot activity
- Database connection issue → Check logs
- Query filter too restrictive → Clear filters

**Verify database has data**:
```bash
docker exec dashboard-dev sqlite3 /app/data/bot.db "SELECT COUNT(*) FROM messages WHERE sender='assistant';"
```

---

### Images not loading

**Check image files exist**:
```bash
docker exec dashboard-dev ls -la /app/data/images/
```

**Check thumbnail generation**:
```bash
docker logs dashboard-dev | grep thumbnail
```

**Clear thumbnail cache**:
```bash
docker exec dashboard-dev rm -rf /app/thumbnails/*
```

---

### Manual controls fail

**Check bot services are accessible**:
```bash
docker exec dashboard-dev python -c "from src.services.image_service import ImageService; print('OK')"
```

**Check OpenAI API key**:
```bash
docker exec dashboard-dev env | grep OPENAI_API_KEY
```

**Check scheduled_tasks table**:
```bash
docker exec dashboard-dev sqlite3 /app/data/bot.db "SELECT * FROM scheduled_tasks WHERE task_type LIKE 'manual_%' ORDER BY created_at DESC LIMIT 5;"
```

---

### Performance issues

**Check database indexes**:
```bash
docker exec dashboard-dev sqlite3 /app/data/bot.db ".indexes messages"
```

**Expected indexes**:
- `idx_messages_timestamp`
- `idx_messages_conversation_sender`

**Create missing indexes** (see data-model.md for SQL)

**Check database size**:
```bash
docker exec dashboard-dev du -h /app/data/bot.db
```

**If database >100MB**, consider archiving old messages

---

## Development Workflow

### Making Backend Changes

1. Edit code in `dashboard/backend/`
2. Flask auto-reloads (if running with `--debug`)
3. Test endpoint: http://localhost:5000/api/activity
4. View logs: `docker logs dashboard-dev -f`

### Making Frontend Changes

1. Edit code in `dashboard/frontend/src/`
2. Vite HMR updates browser automatically
3. Check browser console for errors
4. View network tab for API calls

### Testing API Endpoints

**Using curl**:

```bash
# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password"}' \
  -c cookies.txt

# Get activity log
curl http://localhost:8080/api/activity?page=1&limit=10 \
  -b cookies.txt

# Manual image generation
curl -X POST http://localhost:8080/api/controls/generate-image \
  -H "Content-Type: application/json" \
  -d '{"theme":"celebration"}' \
  -b cookies.txt
```

**Using Postman/Insomnia**:
- Import OpenAPI spec: `specs/002-web-dashboard/contracts/openapi.yaml`
- Set base URL: http://localhost:8080
- Enable cookie jar for session management

---

## Database Access

**SQLite CLI**:

```bash
# Access database
docker exec -it dashboard-dev sqlite3 /app/data/bot.db

# List tables
.tables

# Check messages count
SELECT COUNT(*) FROM messages WHERE sender='assistant';

# Recent images
SELECT id, prompt, status, created_at FROM generated_images ORDER BY created_at DESC LIMIT 5;

# Upcoming events
SELECT task_type, scheduled_time, status FROM scheduled_tasks WHERE status='pending' ORDER BY scheduled_time;

# Exit
.quit
```

---

## Monitoring

### Health Check

**Dashboard health endpoint** (to be added):
```bash
curl http://localhost:8080/api/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "session_storage": "ok",
  "uptime_seconds": 3600
}
```

### Log Monitoring

```bash
# Follow logs
docker logs dashboard-dev -f

# Filter for errors
docker logs dashboard-dev 2>&1 | grep ERROR

# Filter for API requests
docker logs dashboard-dev 2>&1 | grep "GET /api"
```

### Resource Usage

```bash
# Container stats
docker stats dashboard-dev

# Disk usage
docker exec dashboard-dev df -h /app/data
docker exec dashboard-dev df -h /app/sessions
docker exec dashboard-dev df -h /app/thumbnails
```

---

## Production Checklist

Before deploying to production:

- [ ] Change `DASHBOARD_ADMIN_PASSWORD` to strong password (12+ chars)
- [ ] Set `FLASK_ENV=production` in environment
- [ ] Configure HTTPS (reverse proxy or Caddy)
- [ ] Set up log rotation (Docker logging driver)
- [ ] Configure backup for session volume (if persistence needed)
- [ ] Test database read-only mount (`:ro`)
- [ ] Verify thumbnail cache has size limit
- [ ] Set up monitoring/alerting
- [ ] Document password for team (secure storage)
- [ ] Test disaster recovery (container restart, database restore)

---

## Updating Dashboard

### Pull Latest Code

```bash
git pull origin 002-web-dashboard
```

### Rebuild Container

```bash
docker-compose -f docker-compose.dev.yml build dashboard
docker-compose -f docker-compose.dev.yml up -d dashboard
```

### Database Migrations

If schema changes are needed:

```bash
docker exec bot-dev alembic upgrade head
```

Dashboard will automatically see new schema (shared database)

---

## Next Steps

After successful setup:

1. **Explore features**: Test all tabs and functionality
2. **Review logs**: Familiarize yourself with log format
3. **Test manual controls**: Verify bot integration works
4. **Configure alerts**: Set up monitoring for errors
5. **Document password**: Share with team securely
6. **Plan backup strategy**: Sessions and thumbnails (if needed)

---

## Support

**Issues**: Report bugs to project maintainer
**Documentation**: See [plan.md](./plan.md) and [data-model.md](./data-model.md)
**API Reference**: See [contracts/openapi.yaml](./contracts/openapi.yaml)
