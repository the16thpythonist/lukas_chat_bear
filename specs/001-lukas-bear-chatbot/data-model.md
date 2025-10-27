# Data Model: Lukas the Bear Slack Chatbot

**Date**: 2025-10-24
**Feature**: Lukas the Bear Slack Chatbot
**Purpose**: Define database entities and relationships for persistent storage

## Overview

The chatbot requires persistent storage for conversation history, team member tracking, scheduled tasks, and configuration. SQLite provides sufficient performance and simplicity for the expected scale (<50 users, ~500 messages/day).

---

## Entity Definitions

### 1. ConversationSession

**Purpose**: Represents an ongoing or completed conversation between Lukas and a team member

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique conversation identifier |
| team_member_id | UUID | FOREIGN KEY → TeamMember.id, NOT NULL | Participant in conversation |
| channel_type | ENUM('dm', 'channel', 'thread') | NOT NULL | Where conversation occurred |
| channel_id | STRING(50) | NULL | Slack channel ID if channel/thread conversation |
| thread_ts | STRING(50) | NULL | Slack thread timestamp if threaded conversation |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When conversation started |
| last_message_at | TIMESTAMP | NOT NULL | Most recent message timestamp |
| message_count | INTEGER | NOT NULL, DEFAULT 0 | Total messages exchanged |
| total_tokens | INTEGER | NOT NULL, DEFAULT 0 | Cumulative token usage for cost tracking |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | FALSE when conversation considered complete |
| context_summary | TEXT | NULL | Optional summary for very long conversations (Phase 2) |

**Indexes**:
- `idx_team_member_active` ON (team_member_id, is_active) - Retrieve active conversations for user
- `idx_last_message_at` ON (last_message_at) - Cleanup old conversations
- `idx_thread_ts` ON (thread_ts) - Fast thread lookup

**Relationships**:
- Many ConversationSessions → One TeamMember
- One ConversationSession → Many Messages

**Business Rules**:
- Conversations marked inactive after 24 hours of no activity
- Conversations older than 90 days archived/deleted (configurable)
- `channel_type = 'dm'` implies `channel_id` and `thread_ts` are NULL
- `thread_ts` must match Slack's timestamp format (e.g., "1234567890.123456")

---

### 2. Message

**Purpose**: Individual messages within a conversation

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique message identifier |
| conversation_id | UUID | FOREIGN KEY → ConversationSession.id, NOT NULL | Parent conversation |
| sender_type | ENUM('user', 'bot') | NOT NULL | Who sent this message |
| content | TEXT | NOT NULL | Message text content |
| timestamp | TIMESTAMP | NOT NULL, DEFAULT NOW | When message was sent |
| slack_ts | STRING(50) | NULL | Slack message timestamp (for editing/threading) |
| token_count | INTEGER | NOT NULL, DEFAULT 0 | Estimated tokens in this message |
| metadata | JSON | NULL | Additional data (reactions, attachments, etc.) |

**Indexes**:
- `idx_conversation_timestamp` ON (conversation_id, timestamp) - Retrieve conversation history in order
- `idx_slack_ts` ON (slack_ts) - Fast lookup by Slack timestamp

**Relationships**:
- Many Messages → One ConversationSession

**Business Rules**:
- Messages ordered by `timestamp` within a conversation
- Token count calculated using `tiktoken` on message creation
- `sender_type = 'user'` for team member messages
- `sender_type = 'bot'` for Lukas's responses
- `metadata` stores JSON like `{"reactions": ["thumbsup"], "attachments": []}`

---

### 3. TeamMember

**Purpose**: Represents a Slack workspace user

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Internal user identifier |
| slack_user_id | STRING(50) | UNIQUE, NOT NULL | Slack's user ID (e.g., "U123ABC456") |
| display_name | STRING(100) | NOT NULL | User's display name from Slack |
| real_name | STRING(150) | NULL | User's full name from Slack profile |
| is_admin | BOOLEAN | NOT NULL, DEFAULT FALSE | Admin privileges for configuration commands |
| is_bot | BOOLEAN | NOT NULL, DEFAULT FALSE | Filter out other bots |
| last_proactive_dm_at | TIMESTAMP | NULL | When Lukas last initiated DM to this user |
| total_messages_sent | INTEGER | NOT NULL, DEFAULT 0 | Engagement metric |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When user first interacted with bot |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Last profile sync from Slack |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | FALSE if user deactivated in Slack |

**Indexes**:
- `idx_slack_user_id` ON (slack_user_id) - Fast lookup by Slack ID
- `idx_last_proactive_dm_at` ON (last_proactive_dm_at) WHERE is_active = TRUE - Select users for random DM
- `idx_is_admin` ON (is_admin) - Permission checks

**Relationships**:
- One TeamMember → Many ConversationSessions
- One TeamMember → Many ScheduledTasks (as recipient)

**Business Rules**:
- `slack_user_id` synced from Slack API periodically
- `is_bot = TRUE` excludes from random DM selection
- `is_active = FALSE` when user leaves workspace
- Admins can execute configuration commands (set intervals, update persona)
- `last_proactive_dm_at` updated when random DM sent to ensure fair distribution

---

### 4. ScheduledTask

**Purpose**: Represents time-based tasks (proactive DMs, image posts, maintenance)

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique task identifier |
| job_id | STRING(100) | UNIQUE, NOT NULL | APScheduler job ID |
| task_type | ENUM('random_dm', 'image_post', 'cleanup', 'reminder') | NOT NULL | Type of scheduled action |
| target_type | ENUM('user', 'channel', 'system') | NOT NULL | Who/what receives this task |
| target_id | STRING(50) | NULL | Slack user/channel ID (NULL for system tasks) |
| scheduled_at | TIMESTAMP | NOT NULL | When task should execute |
| executed_at | TIMESTAMP | NULL | When task actually executed (NULL if pending) |
| status | ENUM('pending', 'executing', 'completed', 'failed', 'cancelled') | NOT NULL, DEFAULT 'pending' | Execution status |
| retry_count | INTEGER | NOT NULL, DEFAULT 0 | How many times task was retried |
| error_message | TEXT | NULL | Error details if status = 'failed' |
| metadata | JSON | NULL | Task-specific data (e.g., DM content, image prompt) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When task was created |

**Indexes**:
- `idx_job_id` ON (job_id) - APScheduler job lookup
- `idx_scheduled_at_status` ON (scheduled_at, status) - Find pending tasks
- `idx_task_type_status` ON (task_type, status) - Task type filtering

**Relationships**:
- ScheduledTask may reference TeamMember via `target_id` (not enforced FK due to channel targets)

**Business Rules**:
- `task_type = 'random_dm'` creates DM to user specified in `target_id`
- `task_type = 'image_post'` posts to channel in `target_id`
- `task_type = 'cleanup'` has `target_type = 'system'`, `target_id = NULL`
- `task_type = 'reminder'` used for user-requested scheduled messages
- Failed tasks retried up to 3 times before marking permanently failed
- APScheduler `job_id` must match for job updates/cancellations
- `metadata` examples:
  - Random DM: `{"message_template": "check_in", "selected_at": "2025-10-24T10:00:00Z"}`
  - Image post: `{"prompt": "bear eating honey", "theme": "fall"}`

---

### 5. Configuration

**Purpose**: Runtime configuration parameters (intervals, probabilities, persona)

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Config entry identifier |
| key | STRING(100) | UNIQUE, NOT NULL | Configuration parameter name |
| value | TEXT | NOT NULL | Configuration value (JSON serialized for complex types) |
| value_type | ENUM('string', 'integer', 'float', 'boolean', 'json') | NOT NULL | Type for deserialization |
| description | TEXT | NOT NULL | Human-readable explanation of this setting |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Last configuration change |
| updated_by_user_id | UUID | FOREIGN KEY → TeamMember.id, NULL | Who changed this (NULL if system default) |

**Indexes**:
- `idx_key` ON (key) - Fast config lookups

**Relationships**:
- Configuration may reference TeamMember via `updated_by_user_id`

**Business Rules**:
- Configuration loaded into memory on bot startup
- Changes persisted immediately and applied without restart (where possible)
- Admin commands update configuration entries
- Example keys:
  - `random_dm_interval_hours`: "24" (value_type=integer)
  - `thread_response_probability`: "0.20" (value_type=float)
  - `image_post_interval_days`: "7" (value_type=integer)
  - `active_hours`: '{"start": "08:00", "end": "18:00", "timezone": "America/New_York"}' (value_type=json)
  - `persona_system_prompt`: "You are Lukas the Bear..." (value_type=string)

**Default Values**:
- Seeded on first database initialization from `config/config.yml`
- Defaults preserved in version control for easy reset

---

### 6. EngagementEvent

**Purpose**: Audit log of Lukas's proactive channel engagement decisions

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Event identifier |
| channel_id | STRING(50) | NOT NULL | Slack channel ID |
| thread_ts | STRING(50) | NULL | Thread timestamp if responding to thread |
| event_type | ENUM('thread_response', 'reaction', 'ignored') | NOT NULL | Action taken |
| decision_probability | FLOAT | NOT NULL | Configured probability used (0.0-1.0) |
| random_value | FLOAT | NOT NULL | Generated random value for decision |
| engaged | BOOLEAN | NOT NULL | TRUE if Lukas responded/reacted |
| message_id | UUID | FOREIGN KEY → Message.id, NULL | Message created if engaged=TRUE |
| timestamp | TIMESTAMP | NOT NULL, DEFAULT NOW | When decision was made |
| metadata | JSON | NULL | Additional context (thread content summary, activity level) |

**Indexes**:
- `idx_timestamp` ON (timestamp) - Analyze engagement over time
- `idx_engaged` ON (engaged, timestamp) - Count engagement rate
- `idx_channel_thread` ON (channel_id, thread_ts) - Prevent duplicate engagement in same thread

**Relationships**:
- EngagementEvent may reference Message (if Lukas responded)

**Business Rules**:
- Each thread evaluated at most once (check `channel_id + thread_ts` before creating event)
- `engaged = TRUE` when `random_value < decision_probability`
- Provides data for tuning `thread_response_probability` parameter
- `metadata` might include:
  - Thread participant count
  - Thread message count
  - Topic keywords for analysis

---

### 7. GeneratedImage

**Purpose**: Track AI-generated images posted by Lukas

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Image record identifier |
| prompt | TEXT | NOT NULL | DALL-E prompt used |
| image_url | STRING(500) | NOT NULL | URL to generated image (OpenAI hosted) |
| posted_to_channel | STRING(50) | NULL | Channel ID where posted (NULL if generation failed before posting) |
| posted_at | TIMESTAMP | NULL | When image was posted to Slack |
| generation_duration_seconds | FLOAT | NULL | Time taken to generate (for monitoring) |
| cost_usd | FLOAT | NULL | API cost for this generation |
| status | ENUM('generated', 'posted', 'failed') | NOT NULL | Lifecycle status |
| error_message | TEXT | NULL | Error details if status='failed' |
| metadata | JSON | NULL | Theme, occasion, Slack message timestamp |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When generation was requested |

**Indexes**:
- `idx_posted_at` ON (posted_at) - Retrieve recent posts
- `idx_status` ON (status) - Find failed generations for retry

**Business Rules**:
- `image_url` expires after 60 days (DALL-E policy), consider downloading/rehosting
- `cost_usd` calculated based on DALL-E pricing (currently $0.040-0.080 per image)
- `metadata` stores theme info: `{"theme": "halloween", "occasion": null, "slack_ts": "1234567890.123456"}`
- Failed generations logged for debugging and cost tracking

---

## Relationships Diagram

```
TeamMember (1) ──────< (N) ConversationSession (1) ──────< (N) Message
     │                            │
     │                            └──> EngagementEvent (0-1)
     │
     └───────< (N) ScheduledTask
     │
     └───────< (N) Configuration (updated_by)

GeneratedImage (standalone - no direct FK relationships)
```

---

## Data Retention Policy

| Entity | Retention Period | Cleanup Strategy |
|--------|------------------|------------------|
| ConversationSession | 90 days | APScheduler daily job marks old conversations inactive, deletes after retention period |
| Message | 90 days (tied to parent conversation) | Cascade delete when ConversationSession deleted |
| TeamMember | Indefinite (unless user leaves workspace) | Mark `is_active=FALSE`, keep for historical data |
| ScheduledTask | 30 days after completion | Delete completed/failed tasks older than 30 days |
| Configuration | Indefinite | Keep configuration history for audit |
| EngagementEvent | 180 days | Delete old events, keep aggregated statistics |
| GeneratedImage | 365 days | Archive image metadata, note URL expiration |

**Implementation**: APScheduler cron job runs daily at 2am (configured timezone) to execute cleanup queries.

---

## Schema Migration Strategy

**Tool**: Alembic (SQLAlchemy migration tool)

**Process**:
1. Define models in `src/models/*.py` using SQLAlchemy ORM
2. Generate migration with `alembic revision --autogenerate -m "description"`
3. Review generated migration in `migrations/versions/`
4. Apply with `alembic upgrade head`

**Deployment**: Docker entrypoint runs `alembic upgrade head` before starting bot to ensure schema current

---

## Indexes and Performance

**Query Patterns Optimized**:

1. **Retrieve recent conversation**: `(team_member_id, is_active)` index on ConversationSession
2. **Load conversation history**: `(conversation_id, timestamp)` index on Message
3. **Select user for random DM**: `(last_proactive_dm_at, is_active)` filtered index on TeamMember
4. **Check thread already engaged**: `(channel_id, thread_ts)` unique index on EngagementEvent
5. **Find pending scheduled tasks**: `(scheduled_at, status)` composite index on ScheduledTask
6. **Admin permission check**: `is_admin` index on TeamMember

**Estimated Data Volumes** (after 6 months):

- TeamMembers: 50 rows (~10 KB)
- ConversationSessions: ~2,000 active + historical (~500 KB)
- Messages: ~50,000 historical (~10 MB)
- ScheduledTasks: ~500 active + completed (~200 KB)
- Configuration: 20 rows (~5 KB)
- EngagementEvents: ~10,000 (~2 MB)
- GeneratedImages: ~26 (1/week * 26 weeks) (~20 KB)

**Total Database Size**: ~13 MB (well within SQLite's capabilities)

**SQLite Configuration**:
- `journal_mode = WAL` (Write-Ahead Logging) for better concurrency
- `synchronous = NORMAL` (balance durability vs performance)
- Regular VACUUM to reclaim space after deletions

---

## Security Considerations

**No Sensitive Data Storage**:
- API keys/tokens stored in environment variables, NOT database
- Slack user IDs are workspace-scoped (not globally sensitive)
- Message content considered semi-public (team workspace context)

**Access Control**:
- Database file permissions restricted to bot process user
- No direct SQL access exposed to users
- Admin privileges checked via `TeamMember.is_admin` before executing configuration commands

**Backup Strategy**:
- SQLite file backed up via Docker volume snapshots
- Backup frequency: Daily (automated via host cron or Docker volume plugin)
- Retention: Keep 7 daily + 4 weekly backups

---

## Next Steps

After data model approval, proceed to:
1. API Contracts - Define Slack event schemas and any-llm API interfaces
2. Quickstart Guide - Document setup and configuration
3. Implementation Tasks - Generate task breakdown from this model
