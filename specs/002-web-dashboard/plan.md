# Implementation Plan: Admin Web Dashboard for Lukas the Bear

**Branch**: `002-web-dashboard` | **Date**: 2025-10-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-web-dashboard/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a web-based admin dashboard with monitoring and control capabilities for the Lukas the Bear Slack bot. The dashboard will provide visibility into bot activity (message logs, generated images, scheduled events) and allow admins to manually trigger bot actions (image generation, random DMs).

**Technical Approach**: Flask REST API backend + Vue.js 3 frontend, deployed as separate container in docker-compose, sharing SQLite database with main bot via volume mount. Simple password authentication via environment variable, session-based auth with browser-lifetime sessions. Periodic polling (5-10s) for activity log updates.

## Technical Context

**Language/Version**:
- Backend: Python 3.11+ (Flask 3.0+)
- Frontend: JavaScript/TypeScript with Vue.js 3 (Composition API)

**Primary Dependencies**:
- Backend: Flask, Flask-CORS, Flask-Session, SQLAlchemy (shared with bot), python-dotenv
- Frontend: Vue 3, Vue Router, Axios, Vite (build tool)

**Storage**:
- SQLite database (shared with bot via Docker volume)
- Session storage (Flask-Session with filesystem backend)
- Static files for frontend build

**Testing**:
- Backend: pytest, pytest-flask
- Frontend: Vitest (unit), Playwright (e2e for critical flows)

**Target Platform**:
- Backend: Linux container (Alpine-based)
- Frontend: Modern browsers (Chrome, Firefox, Safari, Edge - last 2 versions)

**Project Type**: Web application (separate backend/frontend)

**Performance Goals**:
- Activity log queries < 2s (SC-001)
- Image gallery load < 3s (SC-002)
- Filter operations < 1s (SC-003)
- Manual action feedback < 30s (SC-004)
- Polling updates < 10s (SC-009)

**Constraints**:
- Single shared password auth (no multi-user complexity)
- Read-only database access except for manual action logging
- Must coexist with bot accessing same database (SQLite WAL mode)
- Container must be lightweight (<500MB image size)

**Scale/Scope**:
- Expected dataset: <10k activity log entries, <500 images, <100 scheduled events
- Concurrent users: 1-3 admins typical, <10 max
- Deployment: Single container alongside 2 existing containers (bot, web-search-mcp)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md`:

### Principle 1: Documentation & Code Clarity
- [x] Documentation plan includes API docs for public interfaces (OpenAPI spec for REST endpoints)
- [x] Complex algorithms/logic identified for explanatory comments (database query optimization, polling mechanism)
- [x] Comments will explain "why" and context, not just "what" (rationale for Flask over FastAPI, session management approach)

### Principle 2: Smart Architecture & Design
- [x] Architecture choices justified by concrete current needs (Flask chosen for simplicity, Vue for reactive UI)
- [x] Simpler alternatives considered and documented if rejected (see Complexity Tracking)
- [x] No premature abstractions (direct SQLAlchemy queries, no ORM abstraction layer beyond existing models)
- [x] YAGNI applied: complexity deferred until proven necessary (no WebSocket, no user management, no export features)

### Principle 3: Pragmatic Testing (80/20 Rule)
- [x] Test strategy focuses on critical user journeys (login flow, activity log display, manual controls)
- [x] High-impact business logic identified for testing (authentication, database queries, manual action invocation)
- [x] NOT targeting 100% coverage - only high-value tests planned (skip trivial getters, focus on API contracts)
- [x] Tests planned are maintainable and fast (API integration tests <5s, frontend component tests <2s)

**Status**: ✅ PASSED - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/002-web-dashboard/
├── plan.md              # This file
├── research.md          # Technology choices and best practices
├── data-model.md        # Database entities and relationships
├── quickstart.md        # Setup and deployment guide
├── contracts/           # API contracts (OpenAPI spec)
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Dashboard Backend
dashboard/
├── backend/
│   ├── app.py                 # Flask application entry point
│   ├── config.py              # Configuration and environment variables
│   ├── auth.py                # Authentication middleware
│   ├── models/                # SQLAlchemy models (imported from src/models)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py            # Login/logout endpoints
│   │   ├── activity.py        # Activity log endpoints
│   │   ├── images.py          # Generated images endpoints
│   │   ├── events.py          # Scheduled events endpoints
│   │   └── controls.py        # Manual control endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database.py        # Database connection/session management
│   │   ├── bot_invoker.py     # Invoke bot services for manual controls
│   │   └── query_builder.py   # Reusable database queries
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_activity_api.py
│       ├── test_images_api.py
│       ├── test_events_api.py
│       └── test_controls_api.py
│
├── frontend/
│   ├── public/                # Static assets
│   ├── src/
│   │   ├── main.js            # Vue app entry point
│   │   ├── App.vue            # Root component
│   │   ├── router/
│   │   │   └── index.js       # Vue Router configuration
│   │   ├── views/
│   │   │   ├── Login.vue      # Login page
│   │   │   ├── Dashboard.vue  # Main dashboard layout
│   │   │   ├── ActivityLog.vue
│   │   │   ├── ImagesGallery.vue
│   │   │   ├── ScheduledEvents.vue
│   │   │   └── ManualControls.vue
│   │   ├── components/
│   │   │   ├── ActivityTable.vue
│   │   │   ├── ImageCard.vue
│   │   │   ├── EventTimeline.vue
│   │   │   ├── ControlPanel.vue
│   │   │   └── Pagination.vue
│   │   ├── services/
│   │   │   ├── api.js         # Axios instance with auth interceptor
│   │   │   ├── auth.js        # Auth service (login/logout/session check)
│   │   │   ├── activity.js    # Activity API calls
│   │   │   ├── images.js      # Images API calls
│   │   │   ├── events.js      # Events API calls
│   │   │   └── controls.js    # Manual controls API calls
│   │   ├── composables/
│   │   │   ├── usePolling.js  # Polling hook for auto-refresh
│   │   │   └── usePagination.js # Pagination logic
│   │   └── utils/
│   │       ├── date.js        # Date formatting utilities
│   │       └── filters.js     # Filter/search utilities
│   └── tests/
│       ├── unit/              # Component tests with Vitest
│       └── e2e/               # E2E tests with Playwright
│
├── Dockerfile.dashboard       # Multi-stage build (backend + frontend static)
└── README.md                  # Dashboard-specific documentation

# Docker Configuration Updates
docker-compose.dev.yml         # Add dashboard service
docker-compose.yml             # Add dashboard service (production)

# Shared Code (no changes needed - dashboard imports from src/)
src/
├── models/                    # SQLAlchemy models (shared)
├── services/                  # Bot services (invoked by dashboard)
└── repositories/              # Data access (used by dashboard queries)
```

**Structure Decision**: Web application with separate backend/frontend structure. Backend is Flask REST API, frontend is Vue 3 SPA. Both deployed together in single container (backend serves frontend static files in production). This follows the multi-container pattern established in the project (bot, web-search-mcp, dashboard).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate frontend/backend projects | Clear separation of concerns for REST API + SPA architecture | Mixing Flask templates with modern reactive UI would be more complex and harder to maintain; Vue provides superior UX for polling/filtering/pagination |
| Vue.js framework vs vanilla JS | Reactive data binding essential for polling updates and complex UI state | Vanilla JS would require manual DOM manipulation and state management, increasing code complexity; Vue's Composition API provides cleaner component logic |
| Multi-stage Docker build | Dashboard requires Node.js for frontend build but Python for backend runtime - separating build-time from runtime dependencies | Single-stage build would include 300MB+ Node.js in final image for zero runtime value; bot doesn't need frontend build step so uses simpler single-stage alpine-based image |

**Justification**: The backend/frontend split is standard web architecture, not premature abstraction. Vue is justified by reactive UI requirements (polling, real-time filters). Single-container deployment keeps infrastructure simple while supporting modern SPA patterns.

**Docker Build Justification**: The dashboard requires a multi-stage build because:
1. Frontend build requires Node.js 18+ and npm dependencies (~300MB)
2. Production runtime only needs Python 3.11 and Flask (~150MB)
3. Multi-stage: Stage 1 builds Vue app (Node), Stage 2 copies static files to Python-only container
4. Final image size: ~180MB vs ~480MB with single-stage
5. Bot doesn't need this because it has no frontend build step (pure Python application)

This is not premature optimization - it's standard practice for SPA + API deployments to avoid shipping build tools to production.

## Phase 0: Research

See [research.md](./research.md) for detailed findings.

### Key Research Topics

1. **Flask vs FastAPI for simple REST API**
   - Decision: Flask (simpler, fewer dependencies, better for straightforward CRUD)
   - Rationale: FastAPI's async capabilities not needed for SQLite queries; Flask has simpler middleware model

2. **Vue 3 Composition API vs Options API**
   - Decision: Composition API
   - Rationale: Better code organization for polling logic, easier testing, more explicit reactivity

3. **Session Management Approaches**
   - Decision: Flask-Session with filesystem backend
   - Rationale: No external dependencies (Redis), survives container restart via volume mount, adequate for <10 concurrent users

4. **SQLite Concurrent Access Patterns**
   - Decision: Use existing WAL mode, read-heavy queries, minimal writes
   - Rationale: Dashboard primarily reads data; only writes are manual action logs (low frequency)

5. **Image Thumbnail Strategy**
   - Decision: On-demand thumbnail generation with caching
   - Rationale: Images stored as files; generate thumbnails on first request, cache in filesystem

6. **Frontend Build Strategy**
   - Decision: Vite for dev server, static build served by Flask in production
   - Rationale: Vite provides fast dev experience; production serves pre-built static files (no build step in container)

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](./data-model.md) for complete schema.

**Key Entities** (all existing in bot database):
- `messages` - Bot message history (ActivityLogEntry)
- `generated_images` - Image generation records
- `scheduled_tasks` - Scheduled and manual events
- `team_members` - User directory for recipient display
- `conversations` - Conversation context

**Dashboard-Specific**:
- Sessions stored in `dashboard/backend/flask_session/` directory (not in database)
- No new database tables needed

### API Contracts

See [contracts/openapi.yaml](./contracts/openapi.yaml) for full OpenAPI 3.0 specification.

**Endpoints Summary**:

**Authentication**:
- `POST /api/auth/login` - Authenticate with password
- `POST /api/auth/logout` - End session
- `GET /api/auth/session` - Check session status

**Activity Logs**:
- `GET /api/activity` - List messages (paginated, filterable)
- `GET /api/activity/:id` - Get message details

**Generated Images**:
- `GET /api/images` - List images (paginated, filterable)
- `GET /api/images/:id` - Get image details
- `GET /api/images/:id/thumbnail` - Get thumbnail

**Scheduled Events**:
- `GET /api/events/upcoming` - List pending events
- `GET /api/events/completed` - List historical events

**Manual Controls**:
- `POST /api/controls/generate-image` - Trigger image generation
- `POST /api/controls/send-dm` - Trigger random DM

**Team Members**:
- `GET /api/team` - List team members (for DM recipient dropdown)

### Quickstart

See [quickstart.md](./quickstart.md) for complete setup instructions.

**Development Setup**:
```bash
# Start dev environment
docker-compose -f docker-compose.dev.yml up -d

# Dashboard accessible at http://localhost:8080
# Default password: set in .env as DASHBOARD_ADMIN_PASSWORD

# Backend dev (with auto-reload)
cd dashboard/backend
flask run --debug

# Frontend dev (with HMR)
cd dashboard/frontend
npm run dev
```

**Production Deployment**:
```bash
# Build and start all services
docker-compose up --build -d

# Dashboard accessible at http://localhost:8080
```

## Phase 2: Implementation Tasks

Implementation tasks will be generated via `/speckit.tasks` command after plan approval.

**Task Categories** (preview):
1. **Setup** - Docker configuration, project scaffolding
2. **Backend API** - Flask routes, authentication, database queries
3. **Frontend UI** - Vue components, routing, API integration
4. **Integration** - Manual control bot service invocation
5. **Testing** - API tests, component tests, E2E critical flows
6. **Documentation** - README, API docs, deployment guide

## Post-Design Constitution Check

Re-evaluating constitution compliance after design phase:

### Principle 1: Documentation & Code Clarity ✅
- OpenAPI spec provides API documentation
- Comments planned for database query optimization rationale
- README will explain authentication flow and deployment

### Principle 2: Smart Architecture & Design ✅
- Flask chosen over FastAPI (simpler, adequate for needs)
- No premature abstractions (direct SQLAlchemy, no repository layer beyond existing)
- Single container deployment (simpler than separate frontend/backend containers)
- Complexity justified in Complexity Tracking section

### Principle 3: Pragmatic Testing (80/20 Rule) ✅
- Focus on API contract tests (login, data retrieval, manual controls)
- E2E tests for critical user journey (login → view logs → trigger action)
- No exhaustive component testing - only complex components (polling, pagination)

**Final Status**: ✅ PASSED - Design maintains constitutional compliance

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite concurrent access issues | Medium | Use WAL mode (already enabled), read-heavy workload, connection pooling with short-lived connections |
| Session file storage fills disk | Low | Session cleanup on logout, reasonable session size (<1KB), monitor disk usage |
| Image thumbnail generation slow | Medium | Lazy generation, cache to filesystem, use Pillow with optimized settings |
| Polling overloads database | Low | 5-10s interval reasonable for SQLite, only polls when dashboard visible (use Page Visibility API) |
| Manual controls fail silently | High | Proper error handling, user feedback, logging to scheduled_tasks table |

## Next Steps

1. Review and approve this implementation plan
2. Run `/speckit.tasks` to generate detailed task breakdown
3. Begin implementation following task priorities (P1 → P2 → P3 etc.)
4. Update CLAUDE.md after completion with new technology stack

## Notes

- Dashboard reuses existing SQLAlchemy models from `src/models/` - no duplication needed
- Manual controls invoke existing bot services (ImageService, ProactiveDMService) via Python import
- Frontend build is part of Docker multi-stage build - no runtime dependencies on Node.js
- Session storage uses volume mount to survive container restarts
