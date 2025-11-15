# Research: Admin Web Dashboard Technology Decisions

**Feature**: Admin Web Dashboard for Lukas the Bear
**Date**: 2025-10-28
**Status**: Final Decisions

This document details the technology research and architectural decisions for the admin web dashboard. All decisions are optimized for the specific context: a simple admin monitoring tool with <10 concurrent users, sharing a SQLite database with the main bot.

---

## 1. Flask vs FastAPI for Simple REST APIs

### Decision: **Flask 3.0+**

### Rationale

**Flask is better suited for this project because**:

1. **Simplicity Advantage**: The dashboard needs straightforward CRUD operations (read activity logs, read images, read events, trigger manual actions). Flask's synchronous model is simpler and more direct for these use cases.

2. **No Async Benefits Here**: FastAPI's async capabilities shine with:
   - High-concurrency I/O-bound operations (1000+ concurrent requests)
   - Long-running operations that benefit from async/await
   - Integration with async libraries (aiohttp, asyncpg)

   Our context doesn't match:
   - Expected load: 1-3 concurrent users, <10 max
   - SQLite with SQLAlchemy (synchronous by design)
   - No external async API calls in critical path

3. **Middleware Simplicity**: Flask's before_request/after_request decorators are straightforward for authentication checks. FastAPI's dependency injection is powerful but overkill for a single shared password auth system.

4. **Fewer Dependencies**: Flask installation is lighter and has fewer transitive dependencies compared to FastAPI (which requires Starlette, Pydantic, and uvicorn/gunicorn).

5. **Team Familiarity**: If the team is more familiar with Flask, debugging and maintenance are easier.

### Technical Details

**Flask Implementation**:
```python
from flask import Flask, jsonify, session, request
from functools import wraps

app = Flask(__name__)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/activity')
@require_auth
def get_activity():
    # Simple synchronous database query
    messages = db.session.query(Message).limit(100).all()
    return jsonify([m.to_dict() for m in messages])
```

**Equivalent FastAPI** (more verbose for same functionality):
```python
from fastapi import FastAPI, Depends, HTTPException
from typing import Annotated

app = FastAPI()

async def verify_session(session: Annotated[str, Depends(get_session)]):
    if not session or not session.get('authenticated'):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session

@app.get('/api/activity')
async def get_activity(session: Annotated[dict, Depends(verify_session)]):
    # Async adds no value with synchronous SQLAlchemy
    messages = db.session.query(Message).limit(100).all()
    return [m.to_dict() for m in messages]
```

### Alternatives Considered

**FastAPI Advantages** (not applicable here):
- Automatic OpenAPI documentation generation (we'll write OpenAPI spec manually anyway)
- Pydantic validation (useful for complex input validation - our API is simple)
- Native async support (no async operations in our stack)
- Type hints everywhere (nice-to-have, not critical for small API)

**When to Reconsider**:
- If bot backend is migrated to FastAPI and consistency becomes important
- If async database driver is adopted (aiosqlite)
- If API grows to >20 endpoints with complex validation needs
- If external async APIs are integrated (webhooks, SSE, WebSockets)

### Trade-offs

| Aspect | Flask | FastAPI |
|--------|-------|---------|
| Learning curve | Shallow | Steeper (async, dependencies) |
| Boilerplate | Minimal | More (Pydantic models, dependencies) |
| Performance | ~100-500 req/s | ~1000-2000 req/s (async) |
| Our workload | 1-10 concurrent users | Overkill |
| Documentation | Manual OpenAPI spec | Auto-generated |
| Session management | Flask-Session (mature) | Requires third-party solution |

**Conclusion**: Flask's simplicity wins for a synchronous, low-concurrency admin tool.

---

## 2. Vue 3 Composition API vs Options API

### Decision: **Composition API**

### Rationale

**Composition API is superior for this dashboard because**:

1. **Polling Logic Reusability**: The dashboard needs polling for activity log updates (FR-012). Composition API's `composables/usePolling.js` provides clean reuse:

```javascript
// composables/usePolling.js
import { ref, onMounted, onUnmounted } from 'vue'

export function usePolling(fetchFn, interval = 5000) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  let timerId = null

  const fetch = async () => {
    loading.value = true
    try {
      data.value = await fetchFn()
      error.value = null
    } catch (e) {
      error.value = e
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    fetch() // Initial load
    timerId = setInterval(fetch, interval)
  })

  onUnmounted(() => {
    if (timerId) clearInterval(timerId)
  })

  return { data, loading, error, refresh: fetch }
}
```

**Usage in component**:
```javascript
// views/ActivityLog.vue
import { usePolling } from '@/composables/usePolling'
import { fetchActivityLog } from '@/services/activity'

export default {
  setup() {
    const { data: activities, loading, error, refresh } = usePolling(
      () => fetchActivityLog({ limit: 100 }),
      5000 // Poll every 5 seconds
    )

    return { activities, loading, error, refresh }
  }
}
```

With Options API, this same pattern requires mixins (harder to understand) or duplicated code.

2. **Better Code Organization**: Complex components like `ManualControls.vue` have multiple concerns:
   - Form state (theme input, channel selector)
   - API calls (trigger image generation, trigger DM)
   - Loading states
   - Error handling

   Composition API groups related logic together:

```javascript
// Composition API - Related logic grouped
setup() {
  // Image generation concern
  const imageTheme = ref('')
  const imageChannel = ref('')
  const imageLoading = ref(false)
  const generateImage = async () => { /* ... */ }

  // DM trigger concern
  const selectedUser = ref(null)
  const dmLoading = ref(false)
  const sendDM = async () => { /* ... */ }

  return {
    imageTheme, imageChannel, imageLoading, generateImage,
    selectedUser, dmLoading, sendDM
  }
}
```

Options API scatters this logic across `data()`, `methods`, and `computed`.

3. **Easier Testing**: Composition API functions are pure JavaScript functions, testable without mounting components:

```javascript
// composables/__tests__/usePolling.test.js
import { usePolling } from '../usePolling'
import { describe, it, expect, vi } from 'vitest'

describe('usePolling', () => {
  it('fetches data on mount and at interval', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ data: 'test' })
    const { data, loading } = usePolling(mockFetch, 1000)

    expect(loading.value).toBe(true)
    await nextTick()
    expect(data.value).toEqual({ data: 'test' })
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })
})
```

4. **TypeScript Ready**: If the project adopts TypeScript later, Composition API has better type inference:

```typescript
// Type inference works naturally
const count = ref(0) // Inferred as Ref<number>
const double = computed(() => count.value * 2) // Inferred as ComputedRef<number>
```

Options API requires manual type annotations everywhere.

### Technical Details

**Key Composables for Dashboard**:

1. **`usePolling(fetchFn, interval)`** - Auto-refresh data
2. **`usePagination(items, pageSize)`** - Client-side pagination
3. **`useFilters(items, filterFn)`** - Real-time filtering
4. **`useAuth()`** - Session management (check auth, logout)

**Component Structure Pattern**:
```javascript
// views/ActivityLog.vue
<script>
import { computed } from 'vue'
import { usePolling } from '@/composables/usePolling'
import { usePagination } from '@/composables/usePagination'
import { useFilters } from '@/composables/useFilters'
import { fetchActivityLog } from '@/services/activity'

export default {
  setup() {
    // Data fetching with auto-refresh
    const { data: rawActivities, loading, error } = usePolling(
      fetchActivityLog,
      5000
    )

    // Filtering
    const { filtered, filters, setFilter } = useFilters(
      rawActivities,
      (activity) => {
        if (filters.recipient && activity.recipient !== filters.recipient) return false
        if (filters.dateRange && !isInRange(activity.timestamp, filters.dateRange)) return false
        return true
      }
    )

    // Pagination
    const { page, pageSize, totalPages, paginatedItems } = usePagination(filtered, 50)

    return {
      activities: paginatedItems,
      loading,
      error,
      filters,
      setFilter,
      page,
      totalPages
    }
  }
}
</script>
```

### Alternatives Considered

**Options API Advantages** (less relevant here):
- Familiar to Vue 2 developers (not a concern for new project)
- Simpler for very basic components (<50 lines) (dashboard components are complex)
- Less boilerplate for single-file components (debatable - Composition API is more explicit)

**When to Reconsider**:
- If the team is strictly Vue 2 experienced and refuses to learn Composition API
- If all components are trivial (<50 lines, no shared logic)
- If the project timeline is extremely tight (<1 week) and Options API is faster to prototype

### Trade-offs

| Aspect | Composition API | Options API |
|--------|-----------------|-------------|
| Code reuse | Excellent (composables) | Good (mixins - less clear) |
| Large components | Well-organized | Scattered logic |
| Testing | Easy (pure functions) | Harder (component mounting) |
| Learning curve | Steeper initially | Gentler |
| TypeScript | Excellent | Requires manual types |
| Reactivity | Explicit (ref, reactive) | Implicit (this.x) |

**Conclusion**: Composition API's code organization and reusability benefits outweigh the learning curve for a dashboard with polling, filtering, and pagination logic.

---

## 3. Session Management Approaches

### Decision: **Flask-Session with Filesystem Backend**

### Rationale

**Filesystem sessions are optimal because**:

1. **No External Dependencies**: Redis would require:
   - Another Docker container
   - Another port mapping
   - Another connection to manage
   - Another failure point

   For <10 concurrent users, this overhead is unjustified.

2. **Survives Container Restarts**: Sessions stored in filesystem can be persisted via Docker volume mount:

```yaml
# docker-compose.yml
dashboard:
  volumes:
    - ./data/dashboard_sessions:/app/sessions
    - ./data/lukas.db:/app/data/lukas.db
```

If container restarts, sessions remain valid (users don't need to re-login).

3. **Adequate Performance**: Filesystem I/O for <10 users is negligible:
   - Session read: <1ms (file read from OS cache)
   - Session write: <5ms (file write, buffered)
   - Total sessions: <20 files (active + expired)

4. **Simple Cleanup**: Flask-Session handles cleanup automatically:

```python
from flask_session import Session
from datetime import timedelta

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/app/sessions'
app.config['SESSION_PERMANENT'] = False  # Session expires on browser close
app.config['SESSION_FILE_THRESHOLD'] = 100  # Max session files before cleanup
Session(app)
```

5. **Security Adequate**: For single shared password, filesystem sessions are secure enough:
   - Session IDs are cryptographically random (Flask default)
   - Files are stored with restrictive permissions (0600)
   - No sensitive data in session (just `authenticated: true` flag)

### Technical Details

**Session Structure**:
```python
# Session data stored in /app/sessions/2f4d3c1a-...
{
    'authenticated': True,
    'login_time': '2025-10-28T10:30:00Z',
    '_permanent': False
}
```

**Authentication Flow**:
```python
# routes/auth.py
from flask import session, request, jsonify
import os

@app.route('/api/auth/login', methods=['POST'])
def login():
    password = request.json.get('password')
    expected = os.getenv('DASHBOARD_ADMIN_PASSWORD')

    if not expected:
        return jsonify({'error': 'Server misconfiguration'}), 500

    if password == expected:
        session['authenticated'] = True
        session['login_time'] = datetime.utcnow().isoformat()
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/session', methods=['GET'])
def check_session():
    return jsonify({'authenticated': session.get('authenticated', False)})
```

**Session Middleware** (authentication check for all API routes):
```python
from flask import session, jsonify
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated', False):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Usage
@app.route('/api/activity')
@require_auth
def get_activity():
    # Protected endpoint
    pass
```

### Alternatives Considered

**1. Redis Sessions**

**Pros**:
- Faster than filesystem (in-memory)
- Better for high concurrency (100+ users)
- TTL support built-in
- Distributed sessions (multiple dashboard instances)

**Cons**:
- Requires Redis container (infrastructure complexity)
- Sessions lost on Redis restart unless persistence configured
- Overkill for <10 users

**When to use**: If dashboard scales to 50+ concurrent users or requires distributed deployment.

**2. JWT (Stateless Authentication)**

**Pros**:
- No server-side session storage
- Scales horizontally (stateless)
- Good for microservices

**Cons**:
- Cannot invalidate tokens before expiry (logout doesn't work properly)
- Larger payload (JWT in every request vs session ID cookie)
- More complex to implement (signing, verification, refresh tokens)
- Overkill for single shared password

**Example JWT issue**:
```python
# JWT logout doesn't actually invalidate token
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    # Can only clear client-side cookie
    # Token remains valid until expiry!
    return jsonify({'message': 'Logged out client-side'})
```

**When to use**: If dashboard needs API access from external tools (not just browser) or if stateless horizontal scaling is required.

**3. In-Memory Sessions (Flask Default)**

**Pros**:
- Fastest (no I/O)
- Simplest setup (no configuration)

**Cons**:
- Lost on container restart (users must re-login)
- Not suitable for production

**When to use**: Development only.

### Performance Comparison

| Method | Read Latency | Write Latency | Restart Behavior | Setup Complexity |
|--------|--------------|---------------|------------------|------------------|
| Filesystem | <1ms | <5ms | Persists (volume) | Low |
| Redis | <0.1ms | <0.1ms | Lost (unless RDB) | Medium |
| JWT | 0ms (stateless) | 0ms | N/A (stateless) | High |
| In-Memory | <0.01ms | <0.01ms | Lost | Minimal |

**Conclusion**: Filesystem sessions provide the best balance of simplicity, persistence, and performance for <10 users.

### Trade-offs

| Aspect | Filesystem | Redis | JWT |
|--------|------------|-------|-----|
| Infrastructure | None | Redis container | None |
| Performance | Excellent (<10 users) | Excellent (any scale) | Excellent |
| Session invalidation | Yes (logout works) | Yes (logout works) | No (token valid until expiry) |
| Horizontal scaling | No (shared volume needed) | Yes (distributed) | Yes (stateless) |
| Persistence | Yes (volume mount) | Optional (RDB/AOF) | N/A (stateless) |
| Complexity | Low | Medium | High |

**Recommendation**: Start with filesystem, migrate to Redis only if user count exceeds 50 or distributed deployment is needed.

---

## 4. SQLite Concurrent Access Patterns and WAL Mode

### Decision: **Use Existing WAL Mode + Read-Heavy Pattern**

### Rationale

**WAL mode solves SQLite concurrency challenges**:

1. **What is WAL Mode?**: Write-Ahead Logging allows concurrent reads and writes:
   - Writers write to separate WAL file (no blocking)
   - Readers read from database file (no blocking)
   - Periodic checkpoints merge WAL into main database

2. **Already Enabled**: The bot likely already uses WAL mode. Verify:

```python
# Check WAL mode
import sqlite3
conn = sqlite3.connect('/app/data/lukas.db')
cursor = conn.execute('PRAGMA journal_mode')
mode = cursor.fetchone()[0]
print(f"Journal mode: {mode}")  # Should be 'wal'
```

If not enabled, enable it once:

```python
conn.execute('PRAGMA journal_mode=WAL')
```

3. **Dashboard Access Pattern**: The dashboard is heavily read-biased:
   - 95% reads: Activity logs, images, events (queries)
   - 5% writes: Manual action logging (INSERT into scheduled_tasks)

WAL mode handles this perfectly:
- Bot writes messages, images, events (no contention)
- Dashboard reads messages, images, events (no contention)
- Dashboard writes manual action logs (rare, no contention)

4. **Connection Management**: Use short-lived connections with proper cleanup:

```python
# services/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager

# Connection pool settings
engine = create_engine(
    'sqlite:////app/data/lukas.db',
    connect_args={
        'check_same_thread': False,  # Allow connections across threads
        'timeout': 10.0  # Wait up to 10s for lock
    },
    pool_size=5,  # Max 5 connections
    max_overflow=10,  # Allow 10 extra connections if needed
    pool_pre_ping=True,  # Check connection health before use
    pool_recycle=3600  # Recycle connections every hour
)

SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Usage
def get_activity_log(limit=100):
    with get_db_session() as session:
        messages = session.query(Message).limit(limit).all()
        return [m.to_dict() for m in messages]
```

5. **No Lock Contention**: With WAL + read-heavy workload + connection pooling:
   - Dashboard queries don't block bot writes
   - Bot writes don't block dashboard reads
   - Only conflicts: concurrent writes (rare with dashboard)

### Technical Details

**WAL Mode Benefits**:

| Scenario | Without WAL | With WAL |
|----------|-------------|----------|
| Dashboard reads while bot writes | BLOCKED | NO BLOCK |
| Dashboard writes while bot reads | BLOCKED | NO BLOCK |
| Dashboard reads while dashboard writes | BLOCKED | NO BLOCK |
| Dashboard + bot write simultaneously | BLOCKED | BRIEF LOCK (milliseconds) |

**WAL Mode Limitations**:
- Network filesystems not supported (NFS) → Use local volume mount
- Slightly larger disk usage (WAL file + main database) → Negligible for <10k records
- Manual checkpoint needed for optimization → Auto-checkpoint every 1000 pages

**Checkpoint Configuration**:
```python
# Optimize WAL checkpoints
conn.execute('PRAGMA wal_autocheckpoint=1000')  # Checkpoint every 1000 pages (~4MB)
```

**Monitoring WAL Size**:
```python
def check_wal_size():
    import os
    db_path = '/app/data/lukas.db'
    wal_path = f'{db_path}-wal'
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
        print(f"WAL size: {wal_size / 1024 / 1024:.2f} MB")
        if wal_size > 10 * 1024 * 1024:  # >10MB
            print("WAL is large, consider manual checkpoint")
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
```

### Alternatives Considered

**1. Serialize All Access (Lock Everything)**

**Approach**: Use file locks or application-level locking to serialize bot + dashboard access.

**Pros**:
- Guarantees no conflicts
- Simple to reason about

**Cons**:
- Dashboard queries block bot writes (unacceptable)
- Bot writes block dashboard queries (poor UX)
- Negates SQLite's concurrency capabilities

**Conclusion**: Defeats purpose of WAL mode.

**2. Separate Read Replica Database**

**Approach**: Periodically copy database to read-only replica for dashboard.

**Pros**:
- No lock contention
- Dashboard queries isolated

**Cons**:
- Stale data (replication lag)
- Disk space (2x database size)
- Complexity (replication script)

**Conclusion**: Overkill for <10 users, WAL mode sufficient.

**3. Migrate to PostgreSQL**

**Pros**:
- Better concurrency (MVCC)
- Better for write-heavy workloads
- No WAL mode quirks

**Cons**:
- Requires PostgreSQL container (infrastructure)
- Migration effort (schema, bot code changes)
- Overkill for lightweight admin tool

**Conclusion**: Only if bot itself needs PostgreSQL features (complex queries, full-text search, spatial data).

### Query Optimization

**Index Strategy**: Ensure indexes exist for dashboard queries.

**Activity Log Queries**:
```sql
-- Index for date range queries
CREATE INDEX idx_messages_timestamp ON messages(timestamp);

-- Index for recipient filtering
CREATE INDEX idx_messages_user_id ON messages(user_id);

-- Composite index for common filters
CREATE INDEX idx_messages_user_timestamp ON messages(user_id, timestamp);
```

**Image Gallery Queries**:
```sql
-- Index for status filtering
CREATE INDEX idx_generated_images_status ON generated_images(status);

-- Index for date range queries
CREATE INDEX idx_generated_images_created_at ON generated_images(created_at);
```

**Scheduled Events Queries**:
```sql
-- Index for upcoming events
CREATE INDEX idx_scheduled_tasks_status_scheduled_time ON scheduled_tasks(status, scheduled_time);

-- Index for completed events
CREATE INDEX idx_scheduled_tasks_executed_at ON scheduled_tasks(executed_at);
```

**Query Performance Goals**:
- Activity log query (<1000 rows): <100ms
- Image gallery query (<100 images): <50ms
- Scheduled events query (<50 events): <20ms

**Pagination**: Use LIMIT/OFFSET with ORDER BY for efficient pagination:

```python
def get_paginated_activities(page=1, page_size=50):
    with get_db_session() as session:
        offset = (page - 1) * page_size
        messages = (
            session.query(Message)
            .order_by(Message.timestamp.desc())
            .limit(page_size)
            .offset(offset)
            .all()
        )
        total = session.query(Message).count()
        return {
            'data': [m.to_dict() for m in messages],
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size
        }
```

### Trade-offs

| Approach | Concurrency | Complexity | Data Freshness | Infrastructure |
|----------|-------------|------------|----------------|----------------|
| WAL Mode | Excellent | Low | Real-time | None |
| Serialized Access | Poor | Low | Real-time | None |
| Read Replica | Excellent | Medium | Delayed (seconds) | Minimal |
| PostgreSQL | Excellent | High | Real-time | PostgreSQL container |

**Conclusion**: WAL mode with read-heavy pattern and connection pooling provides excellent concurrency with zero additional infrastructure.

### When to Reconsider

- Bot + dashboard generate >100 writes/sec → PostgreSQL
- Database size exceeds 1GB → PostgreSQL (better for large datasets)
- Complex analytical queries needed → PostgreSQL (better query planner)
- Need full-text search, JSON queries, or spatial data → PostgreSQL

---

## 5. Image Thumbnail Generation Strategies

### Decision: **On-Demand Generation with Filesystem Caching**

### Rationale

**Lazy generation is optimal because**:

1. **Avoid Upfront Cost**: Generating thumbnails for all images at import time wastes CPU/disk:
   - Many images may never be viewed
   - Dashboard usage is sporadic (admin checks occasionally)
   - Bot generates images but dashboard views are infrequent

2. **Simple Caching**: Filesystem caching is sufficient:

```python
# services/thumbnail.py
from PIL import Image
import os
from pathlib import Path

THUMBNAIL_DIR = '/app/data/thumbnails'
THUMBNAIL_SIZE = (300, 300)

def get_thumbnail_path(image_id):
    return os.path.join(THUMBNAIL_DIR, f'{image_id}_thumb.jpg')

def generate_thumbnail(image_path, image_id):
    """Generate thumbnail and cache to filesystem."""
    thumbnail_path = get_thumbnail_path(image_id)

    # Return cached thumbnail if exists
    if os.path.exists(thumbnail_path):
        return thumbnail_path

    # Ensure thumbnail directory exists
    Path(THUMBNAIL_DIR).mkdir(parents=True, exist_ok=True)

    # Generate thumbnail
    with Image.open(image_path) as img:
        # Preserve aspect ratio
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        # Save as JPEG (smaller than PNG)
        img.convert('RGB').save(thumbnail_path, 'JPEG', quality=85, optimize=True)

    return thumbnail_path
```

3. **Flask Endpoint**:

```python
# routes/images.py
from flask import send_file
from services.thumbnail import generate_thumbnail

@app.route('/api/images/<image_id>/thumbnail')
@require_auth
def get_thumbnail(image_id):
    # Get image record from database
    with get_db_session() as session:
        image = session.query(GeneratedImage).filter_by(id=image_id).first()
        if not image:
            return jsonify({'error': 'Image not found'}), 404

        # Parse image URL to get filesystem path
        # Assuming image_url is like 'file:///app/data/images/abc123.jpg'
        image_path = image.image_url.replace('file://', '')

        # Generate or retrieve cached thumbnail
        thumbnail_path = generate_thumbnail(image_path, image_id)

        # Serve thumbnail with caching headers
        return send_file(
            thumbnail_path,
            mimetype='image/jpeg',
            max_age=86400  # Cache for 24 hours
        )
```

4. **Performance Characteristics**:
   - First request: 100-300ms (generate + save)
   - Subsequent requests: <10ms (serve cached file)
   - Disk usage: ~50KB per thumbnail (vs ~2MB original)

5. **Cleanup Strategy**: Delete old thumbnails periodically:

```python
def cleanup_old_thumbnails(days=30):
    """Delete thumbnails older than N days."""
    import time
    cutoff = time.time() - (days * 86400)

    for filename in os.listdir(THUMBNAIL_DIR):
        filepath = os.path.join(THUMBNAIL_DIR, filename)
        if os.path.getmtime(filepath) < cutoff:
            os.remove(filepath)
            print(f"Deleted old thumbnail: {filename}")
```

### Technical Details

**Image Formats**:
- Source: PNG or JPEG (DALL-E generates PNG by default)
- Thumbnail: JPEG (better compression for small sizes)
- Quality: 85 (good balance between size and visual quality)

**Thumbnail Size**: 300x300px is optimal:
- Small enough for fast loading (30-50KB)
- Large enough for visual clarity in gallery grid
- Standard size for image galleries

**Aspect Ratio**: Use `thumbnail()` method to preserve aspect ratio:
```python
img.thumbnail((300, 300), Image.Resampling.LANCZOS)
# If image is 1024x768, thumbnail becomes 300x225 (preserves ratio)
```

**Resampling Algorithm**:
- `LANCZOS`: Best quality (default)
- `BILINEAR`: Faster but lower quality
- `NEAREST`: Fastest but pixelated

Recommendation: Use LANCZOS (quality > speed for infrequent generation).

**Error Handling**:

```python
def generate_thumbnail(image_path, image_id):
    try:
        thumbnail_path = get_thumbnail_path(image_id)

        if os.path.exists(thumbnail_path):
            return thumbnail_path

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        Path(THUMBNAIL_DIR).mkdir(parents=True, exist_ok=True)

        with Image.open(image_path) as img:
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.convert('RGB').save(thumbnail_path, 'JPEG', quality=85, optimize=True)

        return thumbnail_path

    except Exception as e:
        # Log error and return placeholder thumbnail
        print(f"Thumbnail generation failed for {image_id}: {e}")
        return get_placeholder_thumbnail()

def get_placeholder_thumbnail():
    """Return path to generic placeholder image."""
    return '/app/static/placeholder.jpg'
```

### Alternatives Considered

**1. Pre-Generate All Thumbnails**

**Approach**: Generate thumbnails immediately when bot generates images.

**Pros**:
- Instant loading (no first-request delay)
- Consistent performance

**Cons**:
- Wastes CPU/disk for rarely viewed images
- Requires bot code changes (thumbnail generation in image generation flow)
- Couples bot and dashboard concerns

**Conclusion**: Premature optimization. Dashboard usage is infrequent.

**2. Database BLOB Storage**

**Approach**: Store thumbnail bytes directly in SQLite.

**Pros**:
- Single source of truth (no separate thumbnail directory)
- Transactional (thumbnail + metadata updated together)

**Cons**:
- SQLite performance degrades with BLOBs (especially >100KB)
- Increases database size significantly
- Slower queries (SELECT * becomes expensive)

**Conclusion**: Filesystems are optimized for binary files, databases are not.

**3. Cloud Storage (S3)**

**Approach**: Upload images and thumbnails to S3 (or similar).

**Pros**:
- Offloads storage from bot server
- Better for distributed deployments
- CDN integration for fast serving

**Cons**:
- Requires AWS credentials and configuration
- Additional cost (S3 storage + transfer)
- Network latency for thumbnail generation
- Overkill for <500 images

**Conclusion**: Only if bot deployment moves to cloud or image count exceeds 10k.

**4. Image CDN with Automatic Resizing**

**Approach**: Use Cloudinary, Imgix, or similar service.

**Pros**:
- No generation logic needed (service handles it)
- Multiple sizes on-demand (300x300, 600x600, etc.)
- Automatic optimization (WebP, AVIF)

**Cons**:
- External dependency (service downtime)
- Cost (Cloudinary free tier: 25GB storage, 25GB bandwidth/month)
- Requires image upload to CDN

**Conclusion**: Overkill for <500 images. Use only if serving to public users (not just admins).

### Performance Comparison

| Strategy | First Load | Subsequent Load | Disk Usage | Complexity |
|----------|------------|-----------------|------------|------------|
| On-Demand + Cache | 100-300ms | <10ms | ~50KB/image | Low |
| Pre-Generate | <10ms | <10ms | ~50KB/image | Medium |
| Database BLOB | 50-100ms | 50-100ms | ~50KB/image | Low |
| Cloud Storage | 200-500ms | 100-200ms | 0 (offloaded) | High |
| Image CDN | 100-200ms | 50-100ms | 0 (offloaded) | Medium |

**Conclusion**: On-demand with filesystem caching provides best balance of simplicity, performance, and cost.

### Trade-offs

| Aspect | On-Demand + Cache | Pre-Generate | Cloud Storage |
|--------|-------------------|--------------|---------------|
| First request speed | Slow (300ms) | Fast (<10ms) | Medium (200ms) |
| Infrastructure | None | None | S3/CDN account |
| Bot coupling | None | High (bot generates thumbs) | Medium (upload logic) |
| Disk usage | Minimal (lazy) | High (all thumbs) | None (offloaded) |
| Cost | Free | Free | Paid (storage + bandwidth) |

**Recommendation**: Start with on-demand + filesystem cache. If image gallery becomes heavily used (>1000 views/day), consider pre-generation or CDN.

### When to Reconsider

- Image count exceeds 10k → Cloud storage (S3 + CloudFront)
- Dashboard becomes public-facing → Image CDN (Cloudinary)
- Bot deployment moves to serverless → Must use cloud storage
- Thumbnail generation becomes bottleneck (>1s delay) → Pre-generate or use faster resampling

---

## 6. Frontend Build Strategies

### Decision: **Vite for Development, Static Build Served by Flask**

### Rationale

**Vite + Flask static serving is optimal because**:

1. **Development Experience**: Vite provides excellent DX:
   - Hot Module Replacement (HMR): Changes appear instantly
   - Fast startup: <500ms cold start
   - On-demand compilation: Only compile viewed routes
   - Native ES modules: No bundling during dev

```json
// frontend/package.json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 3000",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

**Development workflow**:
```bash
cd dashboard/frontend
npm run dev
# Access at http://localhost:3000
# Changes appear instantly without refresh
```

2. **Production Deployment**: Single container serves both API and frontend:

**Multi-stage Dockerfile**:
```dockerfile
# Stage 1: Build frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app/frontend
COPY dashboard/frontend/package*.json ./
RUN npm ci
COPY dashboard/frontend ./
RUN npm run build
# Output: /app/frontend/dist (static files)

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# Copy backend code
COPY dashboard/backend ./backend
COPY src ./src

# Copy frontend build artifacts
COPY --from=frontend-build /app/frontend/dist ./backend/static

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expose port
EXPOSE 8080

# Run Flask server (serves API + static files)
CMD ["python", "backend/app.py"]
```

**Flask serves static files**:
```python
# backend/app.py
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='')

# Serve Vue app
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # SPA fallback: serve index.html for all non-API routes
        return send_from_directory(app.static_folder, 'index.html')
```

3. **Build Output**: Vite produces optimized static files:
   - `index.html`: Entry point
   - `assets/index-<hash>.js`: Bundled JavaScript (minified, tree-shaken)
   - `assets/index-<hash>.css`: Bundled CSS (minified)
   - Hash-based filenames enable long-term caching

4. **No Runtime Dependencies**: Production container doesn't need Node.js:
   - Frontend build happens during Docker build (CI/CD)
   - Runtime only needs Python + Flask
   - Smaller image size (~200MB Python vs ~800MB Python + Node)

5. **Configuration**:

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // Proxy API requests to Flask backend during dev
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks: {
          // Split vendor code for better caching
          'vendor': ['vue', 'vue-router', 'axios']
        }
      }
    }
  }
})
```

### Technical Details

**Development Mode**:
- Frontend: Vite dev server (http://localhost:3000)
- Backend: Flask dev server (http://localhost:8080)
- API proxy: Vite proxies `/api/*` to Flask

**Production Mode**:
- Frontend: Static files in Flask's `static/` folder
- Backend: Flask serves API + static files (http://localhost:8080)
- SPA routing: Flask fallback to `index.html` for client-side routes

**Build Performance**:
- Cold build: ~10-20s (npm install + vite build)
- Incremental build: ~2-5s (cached dependencies)
- Build output size: ~300-500KB (gzipped)

**Asset Handling**:
```javascript
// Reference assets in Vue components
<template>
  <img :src="logoUrl" alt="Logo">
</template>

<script>
import { ref } from 'vue'
import logoUrl from '@/assets/logo.png'

export default {
  setup() {
    return { logoUrl }
  }
}
</script>
```

Vite processes images:
- Small images (<10KB): Inlined as base64
- Large images: Copied to `assets/` with hash in filename

### Alternatives Considered

**1. Webpack**

**Pros**:
- Mature ecosystem (been around since 2014)
- More plugins available
- Well-documented

**Cons**:
- Slower build times (30-60s vs 10-20s for Vite)
- Slower dev server startup (5-10s vs <1s for Vite)
- No HMR by default (requires configuration)
- Complex configuration (webpack.config.js can be 100+ lines)

**Comparison**:

| Metric | Vite | Webpack |
|--------|------|---------|
| Cold dev start | <1s | 5-10s |
| HMR update | <100ms | 500-1000ms |
| Production build | 10-20s | 30-60s |
| Config complexity | Low (20 lines) | High (100+ lines) |

**Conclusion**: Vite is strictly better for modern Vue 3 projects.

**2. Separate Frontend Container (nginx)**

**Approach**: Deploy frontend and backend as separate containers:
- Frontend: nginx serves static files (port 80)
- Backend: Flask serves API (port 8080)
- nginx proxies `/api/*` to backend

**Pros**:
- Separation of concerns (frontend/backend deployment independent)
- nginx is faster at serving static files than Flask
- Can scale frontend and backend independently

**Cons**:
- More complex infrastructure (2 containers + proxy config)
- Requires nginx configuration (reverse proxy, CORS)
- Overkill for <10 concurrent users
- Adds another failure point (nginx)

**Conclusion**: Unnecessary complexity for admin tool. Single container is simpler.

**3. Server-Side Rendering (SSR) with Nuxt.js**

**Approach**: Use Nuxt.js (Vue SSR framework) to render pages on server.

**Pros**:
- Better SEO (not relevant for admin dashboard)
- Faster first paint (not relevant for authenticated app)
- Universal rendering (server + client)

**Cons**:
- Requires Node.js in production container
- More complex deployment
- Higher memory usage
- Overkill for admin tool (no SEO needs)

**Conclusion**: SSR is for public-facing websites, not admin dashboards.

### Performance Comparison

| Strategy | Dev Start | Dev HMR | Prod Build | Prod Runtime | Complexity |
|----------|-----------|---------|------------|--------------|------------|
| Vite + Flask | <1s | <100ms | 10-20s | 0 (static) | Low |
| Webpack + Flask | 5-10s | 500ms | 30-60s | 0 (static) | Medium |
| Separate Containers | <1s | <100ms | 10-20s | 0 (static) | High |
| Nuxt.js SSR | 3-5s | 200ms | 20-30s | Node.js | High |

**Conclusion**: Vite + Flask provides best development experience with simplest production deployment.

### Trade-offs

| Aspect | Vite + Flask | Webpack + Flask | Separate Containers |
|--------|--------------|-----------------|---------------------|
| Dev speed | Excellent | Good | Excellent |
| Build speed | Fast | Slow | Fast |
| Infrastructure | Simple (1 container) | Simple (1 container) | Complex (2+ containers) |
| Deployment | Easy | Easy | Complex |
| Runtime deps | Python only | Python only | Python + nginx |

**Recommendation**: Use Vite for dev + static build served by Flask in production.

### When to Reconsider

- If team strongly prefers Webpack (existing expertise) → Use Webpack
- If dashboard becomes public-facing with high traffic (>1000 concurrent users) → Separate frontend container with nginx
- If SEO becomes important (unlikely for admin dashboard) → Nuxt.js SSR
- If dashboard needs complex build pipeline (custom loaders, transforms) → Webpack may have more plugins

---

## Summary of Decisions

| Topic | Decision | Key Reason |
|-------|----------|------------|
| Backend Framework | Flask 3.0+ | Simpler for synchronous CRUD, adequate performance for <10 users |
| Frontend Framework | Vue 3 Composition API | Better code organization for polling/filtering, easier testing |
| Session Management | Flask-Session (filesystem) | No external dependencies, persists via volume, adequate for <10 users |
| Database Concurrency | WAL mode + read-heavy pattern | Excellent concurrency with zero infrastructure, optimal for SQLite |
| Image Thumbnails | On-demand + filesystem cache | Lazy generation avoids waste, simple caching, no infrastructure |
| Frontend Build | Vite (dev) + Flask static (prod) | Fast dev experience, simple production deployment, no runtime Node.js |

All decisions optimize for **simplicity** and **low operational overhead** while meeting the specific needs of a <10 user admin dashboard sharing a SQLite database.

---

## References

- [Flask Documentation](https://flask.palletsprojects.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue 3 Composition API Guide](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Flask-Session Documentation](https://flask-session.readthedocs.io/)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [Pillow (PIL) Documentation](https://pillow.readthedocs.io/)
- [Vite Documentation](https://vitejs.dev/)
