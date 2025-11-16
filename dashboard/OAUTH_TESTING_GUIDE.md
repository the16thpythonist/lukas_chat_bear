# Slack OAuth Testing Guide

Complete guide for testing the OAuth implementation before going live.

## Testing Levels

### Level 1: Unit Tests (No External Dependencies)
**What**: Test individual functions in isolation
**When**: Run before committing code
**Duration**: ~5 seconds

```bash
# Run unit tests
cd dashboard/backend
pytest tests/unit/test_slack_oauth_service.py -v

# Expected output:
# ✓ test_successful_token_exchange
# ✓ test_token_exchange_with_redirect_uri
# ✓ test_token_exchange_slack_error
# ✓ test_successful_file_save
# ✓ test_known_error_codes
# ... (18 tests total)
```

### Level 2: Integration Tests (Mocked Slack API)
**What**: Test complete OAuth flow with mocked Slack responses
**When**: Run before deploying
**Duration**: ~10 seconds

```bash
# Run integration tests
pytest tests/integration/test_oauth_flow.py -v

# Expected output:
# ✓ test_successful_oauth_callback
# ✓ test_oauth_callback_with_user_token
# ✓ test_oauth_callback_missing_code
# ✓ test_oauth_callback_invalid_code
# ... (15 tests total)
```

### Level 3: Manual Testing Script
**What**: Simulate OAuth flow without Slack
**When**: Quick validation during development
**Duration**: ~2 seconds

```bash
# Make script executable
chmod +x dashboard/backend/tests/manual_oauth_test.py

# Run manual tests
cd dashboard/backend
python tests/manual_oauth_test.py

# Expected output:
# ✓ PASS: Token Exchange
# ✓ PASS: File Saving
# ✓ PASS: Error Handling
# ✓ PASS: Callback Endpoint
# 🎉 All tests passed!
```

### Level 4: Local End-to-End Testing (ngrok)
**What**: Real OAuth flow with actual Slack using ngrok tunnel
**When**: Final validation before production
**Duration**: ~2 minutes

This is the **most important** test before going live.

## Level 4: Complete End-to-End Testing Guide

### Prerequisites

1. **Install ngrok**:
   ```bash
   # macOS
   brew install ngrok

   # Linux
   wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
   tar xvzf ngrok-v3-stable-linux-amd64.tgz
   sudo mv ngrok /usr/local/bin/

   # Windows
   # Download from https://ngrok.com/download
   ```

2. **Sign up for ngrok** (optional but recommended):
   ```bash
   # Get auth token from https://dashboard.ngrok.com/get-started/your-authtoken
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

### Step-by-Step Testing

#### 1. Start Your Dashboard

```bash
# Start dashboard in development mode
docker-compose -f docker-compose.dev.yml up -d

# Verify it's running
curl http://localhost:8080/api/health
```

#### 2. Start ngrok Tunnel

```bash
# Create public tunnel to localhost:8080
ngrok http 8080

# You'll see output like:
# Session Status: online
# Forwarding: https://abc123xyz.ngrok.io -> http://localhost:8080
```

**IMPORTANT**: Copy the `https://....ngrok.io` URL

#### 3. Configure Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Select your app
3. Click **OAuth & Permissions** in sidebar
4. Under **Redirect URLs**, click **Add New Redirect URL**
5. Paste: `https://YOUR-NGROK-URL.ngrok.io/api/oauth/callback`
6. Click **Add** then **Save URLs**

#### 4. Get Installation URL

```bash
# Replace with your actual ngrok URL
curl https://YOUR-NGROK-URL.ngrok.io/api/oauth/install

# Response will include:
# {
#   "install_url": "https://slack.com/oauth/v2/authorize?client_id=...",
#   "callback_url": "https://YOUR-NGROK-URL.ngrok.io/api/oauth/callback",
#   "configured": true
# }
```

#### 5. Test OAuth Flow

1. **Copy the `install_url`** from previous step
2. **Open it in your browser**
3. **Select a test workspace** (create a free workspace if needed)
4. **Click "Allow"** to authorize the app
5. **You'll be redirected** to the success page showing:
   - ✓ Slack Installation Successful
   - Team name and ID
   - Token file location

#### 6. Verify Tokens Were Saved

```bash
# Check console logs
docker logs dashboard-dev | grep -A 20 "SLACK OAUTH INSTALLATION SUCCESSFUL"

# You should see:
# ========================================
# SLACK OAUTH INSTALLATION SUCCESSFUL
# ========================================
# Team: Your Workspace (T012345)
# Bot Token: xoxb-123456...
# ...

# Check token file was created
docker exec dashboard-dev ls -la /app/data/oauth_tokens/

# View token file
docker exec dashboard-dev cat /app/data/oauth_tokens/tokens_T*_*.json
```

#### 7. Validate Token Format

The token file should contain:

```json
{
  "ok": true,
  "access_token": "xoxb-...",         ← Bot token (copy this)
  "token_type": "bot",
  "scope": "chat:write,users:read,...",
  "bot_user_id": "U012345ABCD",
  "app_id": "A012345WXYZ",
  "team": {
    "id": "T012345",                  ← Team ID
    "name": "Your Workspace"          ← Workspace name
  },
  "authed_user": {
    "id": "U67890",
    "access_token": "xoxp-..."        ← User token (optional)
  },
  "is_enterprise_install": false,
  "installed_at": "2025-01-16T14:30:22Z"
}
```

#### 8. Test the Token

```bash
# Copy the bot token from the file
BOT_TOKEN="xoxb-your-token-here"

# Test it works with Slack API
curl https://slack.com/api/auth.test \
  -H "Authorization: Bearer $BOT_TOKEN"

# Expected response:
# {
#   "ok": true,
#   "url": "https://yourworkspace.slack.com/",
#   "team": "Your Workspace",
#   "user": "lukas-bear",
#   "team_id": "T012345",
#   "user_id": "U012345"
# }
```

✅ **If you see `"ok": true`, your OAuth implementation is working perfectly!**

### Common Issues and Solutions

#### Issue 1: ngrok URL Changes
**Problem**: ngrok generates new URL each restart (free tier)
**Solution**:
- Use same ngrok session (don't restart)
- Or get paid ngrok account for permanent URL
- Or update Slack redirect URL each time

#### Issue 2: "redirect_uri_mismatch" Error
**Problem**: Redirect URL doesn't match Slack app settings
**Solution**:
```bash
# Check configured URL in Slack app settings
# Must exactly match: https://YOUR-NGROK-URL.ngrok.io/api/oauth/callback
# No trailing slash!
```

#### Issue 3: "invalid_client_id" Error
**Problem**: Wrong client credentials
**Solution**:
```bash
# Verify credentials in .env
docker exec dashboard-dev env | grep SLACK_CLIENT

# Should show:
# SLACK_CLIENT_ID=1234567890.1234567890
# SLACK_CLIENT_SECRET=abc...
```

#### Issue 4: Tokens Not Appearing in Logs
**Problem**: Logging not configured
**Solution**:
```bash
# Check if token directory exists
docker exec dashboard-dev ls -la /app/data/oauth_tokens/

# If directory doesn't exist, restart dashboard
docker-compose -f docker-compose.dev.yml restart dashboard-dev
```

#### Issue 5: Can't Access ngrok URL
**Problem**: Firewall or ngrok not running
**Solution**:
```bash
# Verify ngrok is running
curl -I https://YOUR-NGROK-URL.ngrok.io

# Should return HTTP 200 or 302
```

## Pre-Production Checklist

Before using OAuth in production, verify:

- [ ] All unit tests pass (`pytest tests/unit/test_slack_oauth_service.py`)
- [ ] All integration tests pass (`pytest tests/integration/test_oauth_flow.py`)
- [ ] Manual test script passes (`python tests/manual_oauth_test.py`)
- [ ] End-to-end test with ngrok successful
- [ ] Token file created and contains valid JSON
- [ ] Token validated with `auth.test` API
- [ ] Console output shows formatted token information
- [ ] Error handling tested (try invalid code, network issues)
- [ ] Multiple installations work (install on 2+ workspaces)
- [ ] Redirect URL configured in production environment
- [ ] Client credentials secured (not in git, only in .env)

## Quick Test Commands

```bash
# Test everything at once
cd dashboard/backend

# 1. Unit tests
pytest tests/unit/test_slack_oauth_service.py -v

# 2. Integration tests
pytest tests/integration/test_oauth_flow.py -v

# 3. Manual test
python tests/manual_oauth_test.py

# 4. Start ngrok (in separate terminal)
ngrok http 8080

# 5. Test install endpoint
curl http://localhost:8080/api/oauth/install | jq

# All tests passed? You're ready for production! 🚀
```

## Production Deployment

Once all tests pass:

1. **Update production .env**:
   ```bash
   SLACK_CLIENT_ID=your-production-client-id
   SLACK_CLIENT_SECRET=your-production-secret
   SLACK_REDIRECT_URI=https://your-production-domain.com/api/oauth/callback
   ```

2. **Configure production redirect URL** in Slack app settings

3. **Deploy dashboard**:
   ```bash
   docker-compose up --build -d
   ```

4. **Test production endpoint**:
   ```bash
   curl https://your-production-domain.com/api/oauth/install
   ```

5. **Monitor logs**:
   ```bash
   docker logs dashboard -f | grep -i oauth
   ```

## Security Notes

- ✅ Tokens are printed to logs (server-side only, not exposed to users)
- ✅ Token files saved with proper permissions (0644)
- ✅ Client secret never exposed in responses
- ✅ Error messages don't leak sensitive information
- ✅ HTTPS required for production (ngrok provides HTTPS)
- ⚠️  Remember to secure `/app/data/oauth_tokens/` directory
- ⚠️  Rotate credentials if compromised

## Support Resources

- **Slack OAuth Docs**: https://api.slack.com/authentication/oauth-v2
- **ngrok Docs**: https://ngrok.com/docs
- **Test Slack App**: Create free workspace at https://slack.com/create
- **Slack API Tester**: https://api.slack.com/methods/auth.test/test

---

**Questions or issues?** Check logs first:
```bash
docker logs dashboard-dev --tail 100 | grep -i oauth
```
