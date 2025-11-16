# Dashboard Session Authentication Fix

## Problem Summary

The dashboard was logging users out when navigating between tabs, showing "Unauthorized access attempt" errors in the logs.

## Root Causes Identified

### 1. **SESSION_COOKIE_SECURE Issue** (HTTP vs HTTPS)
**Problem**: Dashboard was configured with `SESSION_COOKIE_SECURE = True` in production mode, requiring HTTPS connections. When accessing via HTTP (`http://localhost:8080`), browsers refused to store/send the secure cookie.

**Fix**: Added `SESSION_COOKIE_SECURE` environment variable support to allow HTTP access for local deployments.

**Files Changed**:
- `dashboard/backend/config.py`: Line 43 - Allow override via environment variable
- `docker-compose.yml`: Line 59 - Set `SESSION_COOKIE_SECURE=false`
- `.env`: Line 57 - Documented the option

### 2. **SECRET_KEY Randomization** (Multi-Worker Issue)
**Problem**: The SECRET_KEY was being randomly generated on each app startup using `os.urandom(32).hex()`. In a multi-worker setup (gunicorn with 2 workers):
- Worker 1 signs cookies with KEY_A
- Worker 2 verifies cookies with KEY_B (different!)
- Cookie signature verification fails → unauthorized

**Fix**: Generated a persistent SECRET_KEY and stored it in `.env`

**Files Changed**:
- `.env`: Line 58 - Added persistent `SECRET_KEY=630b2c74bf857225233005910ecc7859ae1f1df88d53631535ee3e685a74203a`

### 3. **CORS Configuration** (Origin Mismatch)
**Problem**: The dashboard's CORS configuration only allowed credentials from `http://localhost:5173` (Vite dev server), but production serves from `http://localhost:8080`. The browser blocked cookie transmission due to CORS policy.

**Fix**: Updated CORS_ORIGINS to include both development and production origins.

**Files Changed**:
- `dashboard/backend/config.py`: Line 50 - Added `http://localhost:8080` to allowed origins

## Changes Made

### 1. `/dashboard/backend/config.py`

```python
# Line 43: Allow SESSION_COOKIE_SECURE override
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'

# Line 50: Allow both dev and production origins
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:8080').split(',')

# Line 75: Remove hardcoded SECURE setting from ProductionConfig
# (Now inherits from base Config class)
```

### 2. `/docker-compose.yml`

```yaml
# Line 59: Allow HTTP session cookies
environment:
  - SESSION_DIR=/app/sessions
  - FLASK_ENV=production
  - SESSION_COOKIE_SECURE=false  # Allow HTTP access
```

### 3. `/.env`

```bash
# Line 57-58: Session and secret configuration
# SESSION_COOKIE_SECURE=false  # Set to 'false' for HTTP access, 'true' for HTTPS only
SECRET_KEY=630b2c74bf857225233005910ecc7859ae1f1df88d53631535ee3e685a74203a
```

## Verification

After applying all fixes:

1. **Session Cookie Headers** (correct):
   ```
   Set-Cookie: session=...; HttpOnly; Path=/; SameSite=Lax
   ```
   (No `Secure` flag, allowing HTTP transmission)

2. **CORS Headers** (correct):
   ```
   Access-Control-Allow-Origin: http://localhost:8080
   Access-Control-Allow-Credentials: true
   ```

3. **Persistent SECRET_KEY**: All workers use the same key for signing/verification

4. **Authentication Flow**: Login → Navigate to different tabs → Session persists ✓

## Security Notes

### For Production with HTTPS

If deploying with HTTPS, update these settings for better security:

**`.env`**:
```bash
SESSION_COOKIE_SECURE=true
```

**OR in `docker-compose.yml`**:
```yaml
environment:
  - SESSION_COOKIE_SECURE=true
```

### SECRET_KEY Management

- **Current**: SECRET_KEY is stored in `.env` (suitable for single-server deployments)
- **For production**: Consider using a secrets management system (HashiCorp Vault, AWS Secrets Manager, etc.)
- **Never commit**: Ensure `.env` is in `.gitignore`

## Testing

Test the fix by:

1. Access dashboard at `http://localhost:8080`
2. Login with your password
3. Navigate between tabs (Activity, Images, Manual Controls, etc.)
4. Verify you stay logged in without redirects to login page

## Troubleshooting

If you still experience issues:

1. **Clear browser cache and cookies** for `localhost:8080`
2. **Check browser console** for CORS errors
3. **Verify containers are healthy**: `docker ps`
4. **Check logs**: `docker logs lukas-dashboard`
5. **Restart containers**: `docker-compose -f docker-compose.yml restart dashboard`

## Additional Notes

- Session files are stored in `/app/sessions` (Docker volume `dashboard-sessions`)
- Sessions expire when browser closes (`SESSION_PERMANENT = False`)
- Multi-worker setup requires persistent SECRET_KEY (already configured)
