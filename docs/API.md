# API Documentation

This document describes all HTTP APIs in the Lukas the Bear project.

## 📋 Table of Contents

- [Overview](#overview)
- [Dashboard Backend API](#dashboard-backend-api)
  - [Authentication](#authentication)
  - [Analytics](#analytics)
  - [Manual Controls](#manual-controls)
  - [Task History](#task-history)
  - [Image Gallery](#image-gallery)
  - [Team Members](#team-members)
- [Bot Internal API](#bot-internal-api)
  - [Health Check](#health-check)
  - [Image Generation](#image-generation)
  - [Proactive DM](#proactive-dm)
  - [Scheduled Events](#scheduled-events)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

---

## Overview

The project exposes two HTTP APIs:

1. **Dashboard Backend API** (port 8080)
   - Public-facing API for dashboard frontend
   - Session-based authentication required
   - JSON responses

2. **Bot Internal API** (port 5001)
   - Internal Docker network only (not exposed to host)
   - Used by dashboard to trigger bot actions
   - No authentication (trusted internal network)

---

## Dashboard Backend API

Base URL: `http://localhost:8080/api`

All endpoints require authentication unless otherwise noted.

### Authentication

#### POST `/api/auth/login`

Authenticate user and create session.

**Request Body**:
```json
{
  "password": "admin-password"
}
```

**Response (200 - Success)**:
```json
{
  "message": "Login successful"
}
```

**Response (401 - Invalid Password)**:
```json
{
  "error": "Invalid password"
}
```

**Side Effects**: Sets secure session cookie

---

#### POST `/api/auth/logout`

End user session.

**Authentication**: Required

**Response (200)**:
```json
{
  "message": "Logout successful"
}
```

**Side Effects**: Clears session cookie

---

#### GET `/api/auth/check`

Check if user is authenticated.

**Authentication**: Not required

**Response (200 - Authenticated)**:
```json
{
  "authenticated": true
}
```

**Response (401 - Not Authenticated)**:
```json
{
  "authenticated": false
}
```

---

### Analytics

#### GET `/api/analytics/overview`

Get high-level bot statistics.

**Authentication**: Required

**Response (200)**:
```json
{
  "total_messages": 1523,
  "total_conversations": 87,
  "active_users": 12,
  "images_generated": 24,
  "uptime_days": 45,
  "last_dm_sent": "2025-10-29T08:30:00Z",
  "next_dm_scheduled": "2025-10-29T20:30:00Z",
  "next_image_scheduled": "2025-11-05T08:30:00Z"
}
```

**Field Descriptions**:
- `total_messages`: Total messages exchanged (user + bot)
- `total_conversations`: Number of unique conversation threads
- `active_users`: Users with at least 1 message sent
- `images_generated`: Total DALL-E images created
- `uptime_days`: Days since bot first started
- `last_dm_sent`: Timestamp of most recent proactive DM
- `next_dm_scheduled`: Timestamp of next scheduled random DM
- `next_image_scheduled`: Timestamp of next scheduled image post

---

#### GET `/api/analytics/engagement`

Get user engagement metrics.

**Authentication**: Required

**Response (200)**:
```json
{
  "most_active_users": [
    {
      "display_name": "John Doe",
      "message_count": 234,
      "last_active": "2025-10-29T10:15:00Z"
    },
    {
      "display_name": "Jane Smith",
      "message_count": 189,
      "last_active": "2025-10-29T09:45:00Z"
    }
  ],
  "recent_conversations": [
    {
      "id": 123,
      "user": "John Doe",
      "started_at": "2025-10-29T08:00:00Z",
      "message_count": 12,
      "last_message": "Thanks for the help!"
    }
  ],
  "engagement_trend": {
    "daily_messages": [45, 67, 52, 89, 71],
    "daily_users": [8, 10, 9, 12, 11]
  }
}
```

**Field Descriptions**:
- `most_active_users`: Top users by message count (limited to 10)
- `recent_conversations`: Latest conversation threads (limited to 10)
- `engagement_trend`: Daily metrics for last 7 days

---

### Manual Controls

#### POST `/api/controls/generate-image`

Manually trigger DALL-E image generation.

**Authentication**: Required

**Rate Limit**: 10 requests per hour per session

**Request Body**:
```json
{
  "theme": "celebration",
  "channel_id": "C123456"
}
```

**Parameters**:
- `theme` (optional): Image theme or concept
- `channel_id` (optional): Target Slack channel ID. If omitted, uses default from config.

**Response (200 - Success)**:
```json
{
  "success": true,
  "image_id": 42,
  "image_url": "https://slack-files.com/...",
  "prompt": "A friendly bear celebrating...",
  "message": "Image generated and posted successfully to channel #random"
}
```

**Response (429 - Rate Limited)**:
```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 10 image generations per hour. Please try again later.",
  "retry_after": 3456
}
```

**Response (500 - Bot Error)**:
```json
{
  "success": false,
  "error": "OpenAI API rate limit exceeded",
  "message": "OpenAI API rate limit exceeded - please try again later (cooldown period)"
}
```

**Side Effects**:
- Generates DALL-E image via OpenAI API
- Posts image to specified Slack channel
- Creates audit log in `scheduled_tasks` table with `task_type='manual_image'`

---

#### POST `/api/controls/send-dm`

Manually trigger proactive DM.

**Authentication**: Required

**Rate Limit**: 20 requests per hour per session

**Request Body**:
```json
{
  "user_id": "U123456"
}
```

**Parameters**:
- `user_id` (optional): Target Slack user ID. If omitted, selects random eligible user.

**Response (200 - Success, Targeted DM)**:
```json
{
  "success": true,
  "target_user": "U123456",
  "message_preview": "Hey there! 🐻 How's your day going?",
  "message": "DM sent successfully to user U123456"
}
```

**Response (200 - Success, Random DM)**:
```json
{
  "success": true,
  "target_user": "U789012",
  "message_preview": "Howdy! What can I help you with?",
  "message": "Random DM sent successfully to user U789012"
}
```

**Response (429 - Rate Limited)**:
```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 20 DMs per hour. Please try again later.",
  "retry_after": 2145
}
```

**Response (500 - No Eligible Users)**:
```json
{
  "success": false,
  "error": "No eligible users available",
  "message": "No eligible users available to send DM (all users may have been contacted recently)"
}
```

**Response (500 - User Not Found)**:
```json
{
  "success": false,
  "error": "User U123456 not found in team members",
  "message": "Operation failed: User U123456 not found in team members"
}
```

**Side Effects**:
- Opens DM conversation with target user
- Sends greeting message using persona service
- Updates user's `last_proactive_dm_at` timestamp
- Creates audit log in `scheduled_tasks` table with `task_type='manual_dm'`

**Selection Logic** (when `user_id` omitted):
- Filters users who haven't received DM recently (configurable cooldown)
- Weights by engagement level (more engaged users more likely)
- Randomly selects from eligible pool

---

### Task History

#### GET `/api/tasks/history`

Get paginated task execution history.

**Authentication**: Required

**Query Parameters**:
- `page` (optional, default=1): Page number (1-indexed)
- `per_page` (optional, default=50): Results per page (max 100)
- `task_type` (optional): Filter by task type (`random_dm`, `image_post`, `manual_image`, `manual_dm`)
- `status` (optional): Filter by status (`pending`, `running`, `completed`, `failed`)

**Example Request**:
```
GET /api/tasks/history?page=1&per_page=20&task_type=manual_dm&status=completed
```

**Response (200)**:
```json
{
  "tasks": [
    {
      "id": 456,
      "task_type": "manual_dm",
      "status": "completed",
      "scheduled_time": "2025-10-29T10:00:00Z",
      "executed_at": "2025-10-29T10:00:02Z",
      "metadata": {
        "source": "dashboard_api",
        "target_user": "U123456",
        "random_selection": false
      },
      "target_type": "manual",
      "target_id": "U123456",
      "error_message": null
    },
    {
      "id": 455,
      "task_type": "random_dm",
      "status": "completed",
      "scheduled_time": "2025-10-29T08:00:00Z",
      "executed_at": "2025-10-29T08:00:05Z",
      "metadata": {
        "user_selected": "U789012"
      },
      "target_type": "user",
      "target_id": "U789012",
      "error_message": null
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 234,
    "total_pages": 12,
    "has_next": true,
    "has_prev": false
  }
}
```

**Task Types**:
- `random_dm`: Scheduled random DM
- `image_post`: Scheduled image posting
- `manual_dm`: Manually triggered DM (from dashboard)
- `manual_image`: Manually triggered image generation (from dashboard)

**Task Statuses**:
- `pending`: Scheduled but not yet executed
- `running`: Currently executing
- `completed`: Successfully executed
- `failed`: Execution failed (see `error_message`)

---

### Image Gallery

#### GET `/api/images`

Get paginated list of generated images.

**Authentication**: Required

**Query Parameters**:
- `page` (optional, default=1): Page number (1-indexed)
- `per_page` (optional, default=20): Results per page (max 50)

**Example Request**:
```
GET /api/images?page=1&per_page=10
```

**Response (200)**:
```json
{
  "images": [
    {
      "id": 42,
      "prompt": "A friendly bear celebrating a team victory",
      "image_url": "https://slack-files.com/...",
      "created_at": "2025-10-29T10:30:00Z",
      "channel_id": "C123456",
      "channel_name": "#general"
    },
    {
      "id": 41,
      "prompt": "A bear working on a laptop in a cozy office",
      "image_url": "https://slack-files.com/...",
      "created_at": "2025-10-28T15:20:00Z",
      "channel_id": "C789012",
      "channel_name": "#random"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 24,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

---

#### GET `/api/images/<id>/thumbnail`

Get thumbnail version of image.

**Authentication**: Required

**Path Parameters**:
- `id`: Image ID

**Query Parameters**:
- `size` (optional, default=200): Thumbnail size in pixels (max 400)

**Example Request**:
```
GET /api/images/42/thumbnail?size=150
```

**Response (200)**:
- Content-Type: `image/jpeg`
- Body: JPEG image data

**Response (404)**:
```json
{
  "error": "Image not found"
}
```

**Caching**:
- Thumbnails are generated on first request and cached
- Cache directory: `dashboard/thumbnails/`
- Cache key: `{image_id}_{size}.jpg`

---

### Team Members

#### GET `/api/team`

Get list of active team members.

**Authentication**: Required

**Response (200)**:
```json
[
  {
    "slack_user_id": "U123456",
    "display_name": "John Doe",
    "real_name": "John Doe",
    "message_count": 234
  },
  {
    "slack_user_id": "U789012",
    "display_name": "Jane Smith",
    "real_name": "Jane Smith",
    "message_count": 189
  }
]
```

**Filtering**:
- Only includes users with `total_messages_sent > 0`
- Sorted by `display_name` alphabetically

**Usage**: Populate user dropdown in manual DM control

---

## Bot Internal API

Base URL: `http://lukas-bear-bot-dev:5001/api/internal` (Docker network only)

**⚠️ Security Note**: This API is only accessible within the Docker network and is not exposed to the host machine or internet.

### Health Check

#### GET `/api/internal/health`

Check if bot internal API is healthy and services are initialized.

**Authentication**: None (internal network)

**Response (200 - Healthy)**:
```json
{
  "status": "healthy",
  "services_initialized": true,
  "timestamp": "2025-10-29T10:30:00.123456"
}
```

**Response (503 - Degraded)**:
```json
{
  "status": "degraded",
  "services_initialized": false,
  "timestamp": "2025-10-29T10:30:00.123456"
}
```

**Use Case**: Dashboard checks bot availability before allowing manual controls

---

### Image Generation

#### POST `/api/internal/generate-image`

Trigger DALL-E image generation and post to Slack.

**Authentication**: None (internal network)

**Request Body**:
```json
{
  "theme": "celebration",
  "channel_id": "C123456"
}
```

**Parameters**:
- `theme` (optional): Image theme or concept for DALL-E prompt generation
- `channel_id` (optional): Target Slack channel ID. If omitted, uses default from config.

**Response (200 - Success)**:
```json
{
  "success": true,
  "image_id": 42,
  "image_url": "https://slack-files.com/...",
  "prompt": "A friendly bear celebrating a team victory with confetti"
}
```

**Response (500 - Initialization Failed)**:
```json
{
  "success": false,
  "error": "Bot services failed to initialize"
}
```

**Response (500 - Generation Failed)**:
```json
{
  "success": false,
  "error": "Image service returned no result"
}
```

**Implementation Details**:
- Lazy service initialization on first request
- Uses synchronous Slack client (`WebClient`)
- Creates `scheduled_tasks` audit log entry with `task_type='manual_image'`
- Timeout: 120 seconds (DALL-E generation can be slow)

---

### Proactive DM

#### POST `/api/internal/send-dm`

Send proactive DM to user (random or targeted).

**Authentication**: None (internal network)

**Request Body (Targeted DM)**:
```json
{
  "user_id": "U123456"
}
```

**Request Body (Random DM)**:
```json
{}
```

**Parameters**:
- `user_id` (optional): Target Slack user ID. If omitted, selects random eligible user.

**Response (200 - Success)**:
```json
{
  "success": true,
  "target_user": "U123456",
  "message_preview": "Hey there! 🐻 How's your day going?"
}
```

**Response (500 - No Eligible Users)**:
```json
{
  "success": false,
  "error": "No eligible users available to send DM (all users may have been contacted recently)"
}
```

**Response (500 - User Not Found)**:
```json
{
  "success": false,
  "error": "User U123456 not found in team members"
}
```

**Implementation Details**:
- Uses asynchronous Slack client (`AsyncWebClient`)
- Targeted DM: Uses `_send_targeted_dm_internal()` helper
- Random DM: Uses `ProactiveDMService` with user selection logic
- Creates `scheduled_tasks` audit log entry with `task_type='manual_dm'`
- Timeout: 30 seconds

**DM Selection Logic**:
1. Query team members from database
2. Filter users who haven't received DM recently (cooldown period)
3. Generate greeting message via `PersonaService`
4. Open DM conversation with `conversations_open`
5. Send message with `chat_postMessage`
6. Update user's `last_proactive_dm_at` timestamp

---

### Scheduled Events

#### GET `/api/internal/scheduled-events`

List scheduled channel messages with optional filtering.

**Authentication**: None (internal network)

**Query Parameters**:
- `status` (optional): Filter by status (`pending`, `completed`, `cancelled`, `failed`)
- `limit` (optional, default=100): Maximum number of results
- `offset` (optional, default=0): Skip N results (for pagination)

**Example Requests**:
```
GET /api/internal/scheduled-events
GET /api/internal/scheduled-events?status=pending
GET /api/internal/scheduled-events?status=completed&limit=50&offset=50
```

**Response (200)**:
```json
{
  "success": true,
  "count": 25,
  "events": [
    {
      "id": 1,
      "event_type": "channel_message",
      "scheduled_time": "2025-10-31T15:00:00",
      "target_channel_id": "C123456",
      "target_channel_name": "#general",
      "message": "Meeting reminder: Team sync at 3pm",
      "status": "pending",
      "job_id": "scheduled_event_1",
      "created_by_user_id": "U789012",
      "created_by_user_name": "Admin User",
      "created_at": "2025-10-29T10:00:00",
      "updated_at": null,
      "executed_at": null,
      "error_message": null
    }
  ]
}
```

**Field Descriptions**:
- `id`: Unique event identifier
- `event_type`: Always `channel_message` for one-time scheduled messages
- `scheduled_time`: When the message will be posted (UTC)
- `target_channel_id`: Slack channel ID where message will be posted
- `target_channel_name`: Channel display name (e.g., `#general`)
- `message`: Message content to post
- `status`: Event status (`pending`, `completed`, `cancelled`, `failed`)
- `job_id`: APScheduler job identifier
- `created_by_user_id`: Slack user ID who created the event
- `created_by_user_name`: Display name of creator
- `created_at`: When the event was created
- `updated_at`: When the event was last modified
- `executed_at`: When the event was actually executed
- `error_message`: Error details if execution failed

---

#### POST `/api/internal/scheduled-events`

Create a new scheduled channel message.

**Authentication**: None (internal network)

**Request Body**:
```json
{
  "scheduled_time": "2025-10-31T15:00:00Z",
  "target_channel_id": "C123456",
  "target_channel_name": "#general",
  "message": "Meeting reminder: Team sync at 3pm",
  "created_by_user_id": "U789012",
  "created_by_user_name": "Admin User"
}
```

**Parameters**:
- `scheduled_time` (required): ISO 8601 datetime string in UTC (e.g., `2025-10-31T15:00:00Z`)
- `target_channel_id` (required): Slack channel ID or name (with or without `#`)
- `target_channel_name` (optional): Channel display name (defaults to `target_channel_id`)
- `message` (required): Message content to post
- `created_by_user_id` (optional): Slack user ID of creator
- `created_by_user_name` (optional): Display name of creator

**Response (201 - Success)**:
```json
{
  "success": true,
  "event": {
    "id": 1,
    "event_type": "channel_message",
    "scheduled_time": "2025-10-31T15:00:00",
    "target_channel_id": "C123456",
    "target_channel_name": "#general",
    "message": "Meeting reminder: Team sync at 3pm",
    "status": "pending",
    "job_id": "scheduled_event_1",
    "created_by_user_id": "U789012",
    "created_by_user_name": "Admin User",
    "created_at": "2025-10-29T10:00:00"
  }
}
```

**Response (400 - Validation Error)**:
```json
{
  "success": false,
  "error": "Scheduled time must be in the future"
}
```

**Response (400 - Missing Fields)**:
```json
{
  "error": "Missing required fields: scheduled_time, message"
}
```

**Implementation Details**:
- Creates APScheduler job using `DateTrigger` for one-time execution
- Validates scheduled time is in the future
- Stores naive UTC datetime in database
- Job will execute automatically at scheduled time

---

#### GET `/api/internal/scheduled-events/<id>`

Get details of a specific scheduled event.

**Authentication**: None (internal network)

**Path Parameters**:
- `id`: Event ID (integer)

**Example Request**:
```
GET /api/internal/scheduled-events/1
```

**Response (200)**:
```json
{
  "success": true,
  "event": {
    "id": 1,
    "event_type": "channel_message",
    "scheduled_time": "2025-10-31T15:00:00",
    "target_channel_id": "C123456",
    "target_channel_name": "#general",
    "message": "Meeting reminder: Team sync at 3pm",
    "status": "pending",
    "job_id": "scheduled_event_1",
    "created_by_user_id": "U789012",
    "created_by_user_name": "Admin User",
    "created_at": "2025-10-29T10:00:00"
  }
}
```

**Response (404 - Not Found)**:
```json
{
  "success": false,
  "error": "Event not found"
}
```

---

#### PUT `/api/internal/scheduled-events/<id>`

Update a pending scheduled event's time and/or message.

**Authentication**: None (internal network)

**Path Parameters**:
- `id`: Event ID (integer)

**Request Body** (both fields optional, at least one required):
```json
{
  "scheduled_time": "2025-10-31T16:00:00Z",
  "message": "Updated meeting reminder: Team sync at 4pm"
}
```

**Parameters**:
- `scheduled_time` (optional): New ISO 8601 datetime string in UTC
- `message` (optional): New message content

**Response (200 - Success)**:
```json
{
  "success": true,
  "event": {
    "id": 1,
    "scheduled_time": "2025-10-31T16:00:00",
    "message": "Updated meeting reminder: Team sync at 4pm",
    "updated_at": "2025-10-29T11:30:00",
    ...
  }
}
```

**Response (400 - Cannot Edit)**:
```json
{
  "success": false,
  "error": "Cannot edit event with status 'completed'"
}
```

**Response (400 - Invalid Time)**:
```json
{
  "success": false,
  "error": "Scheduled time must be in the future"
}
```

**Response (404 - Not Found)**:
```json
{
  "success": false,
  "error": "Event not found"
}
```

**Restrictions**:
- Can only edit events with status `pending`
- Cannot change channel (must cancel and create new event)
- Updated scheduled time must be in the future
- Automatically reschedules APScheduler job when time is changed

---

#### DELETE `/api/internal/scheduled-events/<id>`

Cancel a pending scheduled event.

**Authentication**: None (internal network)

**Path Parameters**:
- `id`: Event ID (integer)

**Example Request**:
```
DELETE /api/internal/scheduled-events/1
```

**Response (200 - Success)**:
```json
{
  "success": true,
  "message": "Event cancelled successfully"
}
```

**Response (400 - Cannot Cancel)**:
```json
{
  "success": false,
  "error": "Cannot cancel event with status 'completed'"
}
```

**Response (404 - Not Found)**:
```json
{
  "success": false,
  "error": "Event not found"
}
```

**Side Effects**:
- Removes APScheduler job
- Updates event status to `cancelled`
- Sets `updated_at` timestamp

**Restrictions**:
- Can only cancel events with status `pending`
- Completed, failed, or already cancelled events cannot be cancelled

---

## Error Handling

### Standard Error Response Format

```json
{
  "error": "Brief error identifier",
  "message": "User-friendly error message"
}
```

### Common HTTP Status Codes

| Status | Meaning | When Used |
|--------|---------|-----------|
| 200 | OK | Successful request |
| 401 | Unauthorized | Authentication required or invalid |
| 403 | Forbidden | Authenticated but insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Categories

#### Authentication Errors (401)
```json
{
  "error": "Authentication required",
  "message": "Please log in to access this resource"
}
```

#### Rate Limit Errors (429)
```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 10 image generations per hour. Please try again later.",
  "retry_after": 3456
}
```

#### Bot Service Errors (500)
```json
{
  "success": false,
  "error": "OpenAI API rate limit exceeded",
  "message": "OpenAI API rate limit exceeded - please try again later (cooldown period)"
}
```

#### Validation Errors (400)
```json
{
  "error": "Invalid request",
  "message": "Missing required field: channel_id"
}
```

---

## Rate Limiting

Rate limits are enforced per session (dashboard API) or globally (bot API).

### Dashboard API Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/controls/generate-image` | 10 requests | 1 hour |
| `/api/controls/send-dm` | 20 requests | 1 hour |
| All other endpoints | Unlimited | - |

**Implementation**: In-memory tracking using session ID as key

**Response Headers** (when rate limited):
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1698588000
Retry-After: 3456
```

### Bot Internal API Rate Limits

**No rate limiting** - Trust internal Docker network

However, external service limits may apply:
- **OpenAI API**: 3,500 requests/day, 200 requests/minute (varies by tier)
- **Slack API**: 1+ requests/second (tier-based, with burst allowance)

**Circuit Breaker Protection**: Automatically stops calling failing services after threshold

---

## API Versioning

**Current Version**: v1 (implicit)

**Future Versioning Strategy**:
- URL versioning: `/api/v2/...`
- Breaking changes require new version
- Deprecation notices 90 days before removal

---

## Authentication Details

### Session-Based Authentication

**Flow**:
1. User submits password to `/api/auth/login`
2. Backend validates password against `DASHBOARD_ADMIN_PASSWORD` env var
3. On success, creates secure session with Flask-Session
4. Session cookie set with `HttpOnly`, `Secure`, `SameSite=Lax` flags
5. Subsequent requests include cookie automatically
6. Backend validates session on protected routes

**Session Storage**:
- **Development**: Filesystem (`dashboard/sessions/`)
- **Production**: Redis (recommended) or filesystem

**Session Duration**: 24 hours (configurable in `backend/app.py`)

**Security**:
- Passwords never stored, only compared
- Sessions use cryptographically secure tokens
- Cookies have security flags to prevent XSS/CSRF

---

## CORS Configuration

**Dashboard Backend**:
- Development: Allows `http://localhost:5173` (Vite dev server)
- Production: Same-origin only
- Credentials: Allowed (for session cookies)

**Bot Internal API**:
- No CORS headers (internal network only)

---

**Last Updated**: 2025-10-29
**API Version**: 1.0
