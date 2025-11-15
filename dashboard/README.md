# Lukas the Bear - Admin Web Dashboard

Admin web interface for monitoring and controlling the Lukas the Bear Slack chatbot.

## Features

- **Activity Monitoring**: View chronological log of bot messages with filtering
- **Image Gallery**: Browse generated DALL-E images with metadata
- **Event Scheduler**: View upcoming and completed scheduled tasks
- **Manual Controls**: Trigger image generation and random DMs on-demand

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Bot must be running (creates database)
- `.env` file with `DASHBOARD_ADMIN_PASSWORD` configured

### Development

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker logs dashboard-dev -f

# Access dashboard
open http://localhost:8080
```

**Hot Reload**:
- Backend: Flask auto-reloads on code changes
- Frontend: Vite HMR updates browser automatically

### Production

```bash
# Build and start
docker-compose up --build -d

# Access dashboard
open http://localhost:8080
```

## Architecture

### Backend (Flask)

- **Framework**: Flask 3.0+ with Flask-CORS, Flask-Session
- **Database**: Shared SQLite with bot (read-only access)
- **Authentication**: Single password via `DASHBOARD_ADMIN_PASSWORD`
- **Session**: Filesystem-based (persists across restarts)

**Directory Structure**:
```
backend/
├── app.py              # Flask application factory
├── config.py           # Environment configuration
├── auth.py             # Authentication middleware
├── routes/             # API endpoints
│   ├── auth.py         # Login/logout/session
│   ├── activity.py     # Activity logs
│   ├── images.py       # Generated images
│   ├── events.py       # Scheduled events
│   ├── controls.py     # Manual controls
│   └── team.py         # Team members
├── services/
│   ├── database.py     # SQLAlchemy connection
│   ├── query_builder.py # Query utilities
│   └── bot_invoker.py  # Bot service integration
└── tests/              # Pytest tests
```

### Frontend (Vue 3)

- **Framework**: Vue 3 with Composition API
- **Routing**: Vue Router
- **HTTP Client**: Axios with auth interceptor
- **Build Tool**: Vite

**Directory Structure**:
```
frontend/
├── src/
│   ├── main.js         # Vue app entry
│   ├── App.vue         # Root component
│   ├── router/         # Route configuration
│   ├── views/          # Page components
│   │   ├── Login.vue
│   │   ├── Dashboard.vue
│   │   ├── ActivityLog.vue
│   │   ├── ImagesGallery.vue
│   │   ├── ScheduledEvents.vue
│   │   └── ManualControls.vue
│   ├── components/     # Reusable components
│   ├── services/       # API services
│   ├── composables/    # Vue composables
│   └── utils/          # Helper functions
└── tests/
    ├── unit/           # Vitest component tests
    └── e2e/            # Playwright E2E tests
```

## Environment Variables

Required in `.env`:

```bash
# Dashboard Authentication
DASHBOARD_ADMIN_PASSWORD=your-secure-password-here

# Bot Configuration (already configured)
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
OPENAI_API_KEY=sk-...
```

**Security Note**: Use a strong password (minimum 12 characters, mix of letters, numbers, symbols)

## API Endpoints

### Authentication
- `POST /api/auth/login` - Authenticate with password
- `POST /api/auth/logout` - End session
- `GET /api/auth/session` - Check session status

### Activity Logs
- `GET /api/activity` - List messages (paginated, filterable)
- `GET /api/activity/:id` - Get message details

### Generated Images
- `GET /api/images` - List images (paginated, filterable)
- `GET /api/images/:id` - Get image details
- `GET /api/images/:id/thumbnail` - Get thumbnail

### Scheduled Events
- `GET /api/events/upcoming` - List pending events
- `GET /api/events/completed` - List historical events

### Manual Controls
- `POST /api/controls/generate-image` - Trigger image generation
- `POST /api/controls/send-dm` - Trigger random DM

### Team
- `GET /api/team` - List team members (for DM dropdown)

See `specs/002-web-dashboard/contracts/openapi.yaml` for full API specification.

## Development Workflow

### Backend Development

```bash
# Install dependencies
cd dashboard/backend
pip install -r requirements.txt

# Run Flask dev server (with auto-reload)
export DASHBOARD_ADMIN_PASSWORD=test123
export DATABASE_PATH=../../data/bot.db
flask run --debug --port 5000

# Run tests
pytest
```

### Frontend Development

```bash
# Install dependencies
cd dashboard/frontend
npm install

# Start Vite dev server (with HMR)
npm run dev

# Run unit tests
npm run test:unit

# Run E2E tests
npm run test:e2e
```

### Testing API with curl

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

## Troubleshooting

### Dashboard won't start

```bash
# Check environment variables
docker exec dashboard-dev env | grep DASHBOARD

# Check database exists
docker exec dashboard-dev ls -la /app/data/bot.db

# Check logs
docker logs dashboard-dev --tail 50
```

### Can't log in

```bash
# Verify password is set
echo $DASHBOARD_ADMIN_PASSWORD

# Clear sessions
docker exec dashboard-dev rm -rf /app/sessions/*
```

### Activity log empty

```bash
# Verify database has messages
docker exec dashboard-dev sqlite3 /app/data/bot.db \
  "SELECT COUNT(*) FROM messages WHERE sender='assistant';"
```

### Images not loading

```bash
# Check image files exist
docker exec dashboard-dev ls -la /app/data/images/

# Clear thumbnail cache
docker exec dashboard-dev rm -rf /app/thumbnails/*
```

## Performance

- **Activity log**: <2s load time (up to 100 entries)
- **Image gallery**: <3s load time (up to 50 images)
- **Filter operations**: <1s response time
- **Auto-refresh**: Every 5-10 seconds (pauses when tab hidden)

## Security

- Single password authentication via environment variable
- Session-based auth (filesystem storage)
- Read-only database access (except manual action logging)
- Rate limiting:
  - Manual controls: 10/hour per session
  - General API: 100 requests/minute per IP
- Audit logging for all manual actions
- Secure cookie settings (HttpOnly, SameSite)

## Documentation

- **Feature Spec**: `specs/002-web-dashboard/spec.md`
- **Implementation Plan**: `specs/002-web-dashboard/plan.md`
- **Data Model**: `specs/002-web-dashboard/data-model.md`
- **Quickstart Guide**: `specs/002-web-dashboard/quickstart.md`
- **API Contracts**: `specs/002-web-dashboard/contracts/openapi.yaml`

## License

Part of Lukas the Bear project.
