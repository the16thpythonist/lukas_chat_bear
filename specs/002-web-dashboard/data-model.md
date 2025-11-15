# Data Model: Admin Web Dashboard

**Feature**: 002-web-dashboard
**Last Updated**: 2025-10-28

## Overview

The dashboard primarily **reads** from existing database tables created by the Lukas the Bear bot. No new tables are required. The only write operations are logging manual control actions to the existing `scheduled_tasks` table.

## Database: SQLite (Shared with Bot)

**Access Mode**: Read-heavy (95% reads, 5% writes)
**Concurrency**: WAL mode enabled (allows concurrent reads + single writer)
**Connection Strategy**: Short-lived connections with connection pooling

## Existing Tables (Read-Only for Dashboard)

### messages

**Purpose**: Bot message history (Activity Log source)

**Schema**:
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender TEXT NOT NULL,              -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

**Dashboard Usage**:
- Activity Log display (FR-001)
- Filtering by date range, recipient (FR-002)
- Detail view with conversation context (User Story 1)

**Key Queries**:
```sql
-- Activity log with pagination and filters
SELECT
    m.id, m.content, m.timestamp, m.token_count,
    c.channel_id, c.channel_type, c.user_id
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
WHERE m.sender = 'assistant'
  AND m.timestamp >= :start_date
  AND m.timestamp <= :end_date
  AND (:recipient IS NULL OR c.user_id = :recipient)
ORDER BY m.timestamp DESC
LIMIT :limit OFFSET :offset;
```

**Indexes Needed**:
- `idx_messages_timestamp` on (timestamp) - for date range queries
- `idx_messages_conversation_sender` on (conversation_id, sender) - for filtering bot messages

---

### conversations

**Purpose**: Conversation context for messages

**Schema**:
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,        -- 'dm', 'channel', 'thread'
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Dashboard Usage**:
- Linking messages to recipients (channel/user info)
- Displaying channel type (DM vs channel) in activity log

**Key Queries**:
```sql
-- Get conversation context for message detail view
SELECT
    c.user_id, c.channel_id, c.channel_type, c.started_at,
    tm.display_name, tm.real_name
FROM conversations c
LEFT JOIN team_members tm ON c.user_id = tm.slack_user_id
WHERE c.id = :conversation_id;
```

---

### generated_images

**Purpose**: DALL-E image generation history

**Schema**:
```sql
CREATE TABLE generated_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT NOT NULL,
    image_url TEXT NOT NULL,           -- Local file path or URL
    channel_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',     -- 'pending', 'posted', 'failed'
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    posted_at DATETIME
);
```

**Dashboard Usage**:
- Image gallery display (FR-003)
- Filtering by date range, status (User Story 2)
- Detail view with generation metadata (FR-004)

**Key Queries**:
```sql
-- Image gallery with pagination
SELECT
    id, prompt, image_url, status, channel_id, created_at, error_message
FROM generated_images
WHERE
    (:status IS NULL OR status = :status)
    AND created_at >= :start_date
    AND created_at <= :end_date
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;
```

**Indexes Needed**:
- `idx_generated_images_created_status` on (created_at, status) - for filtered queries

---

### scheduled_tasks

**Purpose**: Scheduled and manual bot actions

**Schema**:
```sql
CREATE TABLE scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,           -- 'reminder', 'random_dm', 'image_post',
                                       -- 'manual_image', 'manual_dm'
    scheduled_time DATETIME NOT NULL,
    target_type TEXT,                  -- 'user', 'channel'
    target_id TEXT,
    status TEXT DEFAULT 'pending',     -- 'pending', 'completed', 'failed', 'cancelled'
    metadata TEXT,                     -- JSON string with task parameters
    executed_at DATETIME,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Dashboard Usage**:
- Scheduled events display (FR-005, FR-006)
- **Manual action logging** (FR-015) - **WRITE ACCESS**
- Sorting by scheduled time (FR-007)

**Key Queries**:
```sql
-- Upcoming events
SELECT
    id, task_type, scheduled_time, target_type, target_id, status, metadata
FROM scheduled_tasks
WHERE status = 'pending'
  AND scheduled_time >= CURRENT_TIMESTAMP
ORDER BY scheduled_time ASC;

-- Completed events
SELECT
    id, task_type, scheduled_time, executed_at, status, metadata, error_message
FROM scheduled_tasks
WHERE status IN ('completed', 'failed', 'cancelled')
ORDER BY executed_at DESC
LIMIT :limit OFFSET :offset;

-- Log manual action (INSERT)
INSERT INTO scheduled_tasks
    (task_type, scheduled_time, target_type, target_id, status, metadata, executed_at)
VALUES
    (:task_type, CURRENT_TIMESTAMP, :target_type, :target_id, 'completed', :metadata, CURRENT_TIMESTAMP);
```

**Indexes Needed**:
- `idx_scheduled_tasks_status_time` on (status, scheduled_time) - for upcoming/completed queries
- `idx_scheduled_tasks_executed` on (executed_at) - for historical queries

**Manual Action Task Types**:
- `manual_image`: Admin-triggered image generation
- `manual_dm`: Admin-triggered random DM

**Metadata Examples** (JSON stored as TEXT):
```json
// manual_image
{
  "source": "dashboard",
  "theme": "celebration",
  "target_channel": "C123456"
}

// manual_dm
{
  "source": "dashboard",
  "target_user": "U789012"  // null if random selection
}
```

---

### team_members

**Purpose**: Team member directory

**Schema**:
```sql
CREATE TABLE team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_user_id TEXT UNIQUE NOT NULL,
    display_name TEXT,
    real_name TEXT,
    is_admin BOOLEAN DEFAULT 0,
    last_message_at DATETIME,
    message_count INTEGER DEFAULT 0,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Dashboard Usage**:
- Displaying recipient names in activity log
- User dropdown for manual DM target selection (FR-009)

**Key Queries**:
```sql
-- Get team member list for dropdown
SELECT slack_user_id, display_name, real_name
FROM team_members
WHERE message_count > 0  -- Only active members
ORDER BY display_name;

-- Get member info for activity log
SELECT display_name, real_name
FROM team_members
WHERE slack_user_id = :user_id;
```

---

### configurations

**Purpose**: Bot configuration settings (read-only for dashboard)

**Schema**:
```sql
CREATE TABLE configurations (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Dashboard Usage**:
- Potentially display bot settings (future enhancement)
- Current implementation: read-only, no dashboard writes

---

## Dashboard-Specific Storage (Non-Database)

### Session Storage

**Location**: `dashboard/backend/flask_session/` directory
**Format**: Filesystem-based pickle files
**Persistence**: Docker volume mount ensures survival across container restarts

**Session Data Structure**:
```python
{
    'authenticated': True,
    'login_time': '2025-10-28T10:30:00Z',
    'session_id': 'uuid-string'
}
```

**Size**: <1KB per session
**Lifetime**: Until browser closed (no server-side expiration)
**Cleanup**: On logout or manual file cleanup script

---

### Image Thumbnail Cache

**Location**: `dashboard/backend/thumbnails/` directory
**Format**: JPEG files
**Naming**: `{image_id}_thumb.jpg`

**Generation Strategy**:
- Lazy: Generated on first request
- Cached: Subsequent requests served from filesystem
- Size: 300x300px, JPEG quality 85

**Cleanup**: Periodic job can remove thumbnails for deleted images

---

## Query Performance Targets

| Query Type | Target | Notes |
|------------|--------|-------|
| Activity log (100 entries) | <2s | SC-001 |
| Image gallery (50 images) | <3s | SC-002 |
| Filter application | <1s | SC-003 |
| Scheduled events (all) | <1s | Typically <100 events |
| Single record detail | <100ms | Simple PK lookup |

---

## Data Flow Diagrams

### Activity Log Query Flow
```
User Request (with filters)
    ↓
Flask Route (/api/activity)
    ↓
Query Builder (build SQL with filters)
    ↓
SQLAlchemy Query
    ↓
SQLite (messages + conversations + team_members JOIN)
    ↓
Result Mapping (dict → JSON)
    ↓
Response (paginated list)
```

### Manual Action Logging Flow
```
User Action (Generate Image)
    ↓
Flask Route (/api/controls/generate-image)
    ↓
Bot Service Invoker (ImageService.generate_and_post)
    ↓
    ├─→ DALL-E API (generate image)
    ├─→ Slack API (post to channel)
    └─→ Database Write (log to scheduled_tasks)
            ↓
Response (success/failure + new task record)
```

---

## Schema Evolution Strategy

**Current**: No dashboard-specific tables needed
**Future**: If analytics/reporting features added, consider:
- Materialized view table for aggregated stats
- Separate `dashboard_sessions` table for persistent sessions

**Migration Approach**: Use Alembic (existing in bot project) for any schema changes

---

## Data Consistency Considerations

1. **Read Consistency**: WAL mode ensures dashboard reads latest committed data
2. **Write Ordering**: Manual action logs written AFTER action completes (not before)
3. **Concurrent Writes**: Bot and dashboard can both write to `scheduled_tasks` (WAL handles conflicts)
4. **Stale Data**: Polling interval (5-10s) means dashboard may show slightly outdated data (acceptable trade-off)

---

## Security Considerations

1. **SQL Injection Prevention**: Use SQLAlchemy parameterized queries (never string concatenation)
2. **Sensitive Data**: Don't expose Slack tokens, API keys, or internal IDs in responses
3. **User IDs**: Display `display_name` instead of Slack IDs where possible
4. **Error Messages**: Generic error messages to frontend, detailed logs server-side

---

## Summary

- ✅ No new tables required (dashboard reads existing bot schema)
- ✅ Only write operation: log manual actions to `scheduled_tasks`
- ✅ Session and cache storage use filesystem (not database)
- ✅ Query performance targets aligned with success criteria
- ✅ Indexes needed for optimal performance documented
