# Slack Event Contracts

**Purpose**: Define Slack event payloads and bot response formats

## Event Types Handled

### 1. Message Event (Direct Messages)

**Trigger**: User sends DM to Lukas

**Slack Payload**:
```json
{
  "type": "message",
  "channel": "D123ABC456",
  "user": "U987XYZ123",
  "text": "Hi Lukas, how are you?",
  "ts": "1234567890.123456",
  "channel_type": "im",
  "event_ts": "1234567890.123456"
}
```

**Bot Response**:
- Acknowledge within 3s
- Call any-llm service with conversation context
- Post response to same channel
- Store message pair in database

**Response Format**:
```json
{
  "channel": "D123ABC456",
  "text": "Hey there! I'm doing great, thanks for asking! 🐻 Just been thinking about honey... as usual. How can I help you today?",
  "thread_ts": null
}
```

---

### 2. Message Event (Channel Mentions)

**Trigger**: User @mentions Lukas in a channel

**Slack Payload**:
```json
{
  "type": "app_mention",
  "channel": "C456DEF789",
  "user": "U987XYZ123",
  "text": "<@U_LUKAS_BOT> Can you post the weekly update to #general?",
  "ts": "1234567890.123456",
  "thread_ts": null,
  "event_ts": "1234567890.123456"
}
```

**Bot Response**:
- Parse command from mention text
- If command detected, execute via command handler
- If casual conversation, respond in thread
- Track engagement in EngagementEvent

---

### 3. Message Event (Channel Threads - Passive Monitoring)

**Trigger**: New message in monitored channel (for probabilistic engagement)

**Slack Payload**:
```json
{
  "type": "message",
  "channel": "C456DEF789",
  "user": "U987XYZ123",
  "text": "Anyone know the status of the research project?",
  "ts": "1234567890.123456",
  "thread_ts": "1234567890.000000",
  "channel_type": "channel"
}
```

**Bot Decision Logic**:
1. Check if thread already engaged (query EngagementEvent)
2. Generate random value (0.0-1.0)
3. Compare to configured `thread_response_probability`
4. If engaged, decide engagement type (text response or emoji reaction)
5. If text response: Call LLM with thread context and post message
6. If emoji reaction: Select contextually appropriate emoji and add reaction
7. Log decision to EngagementEvent

**Bot Response - Text** (if engaged with text):
```json
{
  "channel": "C456DEF789",
  "thread_ts": "1234567890.000000",
  "text": "I've been following the project! From what I've heard, the team is making great progress on Phase 2. @U_PROJECT_LEAD might have more details! 🐻"
}
```

**Bot Response - Reaction** (if engaged with emoji):
```json
{
  "channel": "C456DEF789",
  "timestamp": "1234567890.000000",
  "name": "bear"
}
```
Common reactions: `bear`, `thumbsup`, `tada`, `eyes`, `heart`

---

### 4. Reaction Added Event (Optional - Phase 2)

**Trigger**: User reacts to Lukas's message

**Slack Payload**:
```json
{
  "type": "reaction_added",
  "user": "U987XYZ123",
  "item": {
    "type": "message",
    "channel": "D123ABC456",
    "ts": "1234567890.123456"
  },
  "reaction": "thumbsup",
  "event_ts": "1234567890.789012"
}
```

**Bot Response**:
- No immediate action (MVP)
- Future: Could trigger follow-up engagement

---

## Bot-Initiated Actions

### 1. Proactive Direct Message

**Trigger**: APScheduler interval job executes

**Action**:
1. Select user via `TeamMember` query (not recently contacted)
2. Generate casual check-in message via LLM
3. Post DM to user
4. Update `TeamMember.last_proactive_dm_at`
5. Create ConversationSession

**Message Format**:
```json
{
  "channel": "D123ABC456",
  "text": "Hey! Just checking in - how's your week going? 🐻 I'm here if you need anything or just want to chat!",
  "unfurl_links": false,
  "unfurl_media": false
}
```

---

### 2. AI Image Post

**Trigger**: APScheduler interval job executes

**Action**:
1. Generate context-aware prompt (season, occasion)
2. Call DALL-E API
3. Upload image to Slack
4. Post to configured channel with caption
5. Store in GeneratedImage table

**Message Format**:
```json
{
  "channel": "C789RANDOM",
  "text": "Good morning team! 🍂 I made this to celebrate the beautiful fall weather. Hope it brightens your day! - Lukas 🐻",
  "attachments": [
    {
      "image_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
      "title": "Lukas enjoying autumn",
      "fallback": "Bear image"
    }
  ]
}
```

---

### 3. Command Execution - Channel Post

**Trigger**: User requests "post [message] to #channel"

**Action**:
1. Parse command to extract message and target channel
2. Verify user has permission (not restricted to admins for this command)
3. Post message to specified channel
4. Confirm to requesting user in DM

**Message Format** (to target channel):
```json
{
  "channel": "C123GENERAL",
  "text": "📢 Team meeting at 3pm today! (Posted on behalf of <@U987XYZ123>)"
}
```

**Confirmation** (to requesting user):
```json
{
  "channel": "D123ABC456",
  "text": "Done! I posted your message to #general. ✅"
}
```

---

## Event Handler Signatures

### Python Bolt Framework

```python
from slack_bolt import App

app = App(token=os.environ["SLACK_BOT_TOKEN"])

# DM and channel message handler
@app.event("message")
def handle_message(event, say, ack):
    """
    Handles incoming messages from DMs and channels.

    Args:
        event: Slack event payload
        say: Function to send message response
        ack: Function to acknowledge event receipt
    """
    ack()
    # Delegate to message_handler.py

# Mention handler
@app.event("app_mention")
def handle_mention(event, say, ack):
    """
    Handles @mentions of Lukas in channels.

    Args:
        event: Slack event payload
        say: Function to send message response
        ack: Function to acknowledge event receipt
    """
    ack()
    # Delegate to command_handler.py or message_handler.py
```

---

## Rate Limiting and Error Handling

### Slack API Rate Limits

**Tier 3 Methods** (most messaging APIs):
- Limit: 50+ requests/minute per workspace
- Burst: Short-term higher rates allowed
- Strategy: Slack SDK handles automatic retry with exponential backoff

**Handling 429 (Too Many Requests)**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def post_message_with_retry(channel, text):
    """
    Posts message with automatic retry on rate limits.
    """
    return client.chat_postMessage(channel=channel, text=text)
```

### Error Responses

**Network Errors**:
- Log error with context (channel, user, message preview)
- Return fallback response to user: "I'm having trouble connecting right now, please try again in a moment!"

**Permission Errors**:
- Log error (may indicate bot not invited to channel)
- Return to user: "I don't have access to that channel. Make sure I'm invited!"

**Content Moderation Failures**:
- Log blocked content for review
- Return to user: "I can't process that message. Let's talk about something else!"

---

## Slack Permissions (OAuth Scopes)

Required bot token scopes:
- `channels:history` - Read general channel messages
- `channels:read` - List workspace channels
- `chat:write` - Post messages
- `im:history` - Read direct messages
- `im:write` - Send direct messages
- `users:read` - Access team member profiles
- `files:write` - Upload generated images
- `reactions:write` - Add emoji reactions to messages
- `app_mentions:read` - Receive @mentions

---

## Socket Mode Configuration

**Connection**:
- Use `SocketModeHandler` from Slack Bolt
- WebSocket URL: Managed by SDK
- Automatic reconnection on disconnect

**Benefits**:
- No public webhook endpoint required
- Easier local development
- Automatic event batching

**Trade-offs**:
- Requires persistent connection
- Single instance (no horizontal scaling without sticky sessions)
- Acceptable for current scope (<50 users)

**Future Migration** (if needed):
- Switch to Events API for multi-instance deployment
- Requires public HTTPS endpoint
- No code changes to event handlers

---

## Testing Contracts

### Unit Tests (Mocked Slack Events)

```python
def test_handle_dm_message():
    """Test DM message handling with mocked Slack event."""
    event = {
        "type": "message",
        "channel": "D123ABC456",
        "user": "U987XYZ123",
        "text": "Hello Lukas",
        "ts": "1234567890.123456",
        "channel_type": "im"
    }

    response = handle_message(event)

    assert response["channel"] == "D123ABC456"
    assert "bear" in response["text"].lower()  # Persona check
```

### Integration Tests (Test Workspace)

1. Create dedicated Slack workspace for testing
2. Use test bot token
3. Automated tests post events via Slack API
4. Verify bot responses
5. Clean up test data after each run

**Test Scenarios**:
- Send DM, verify response within 5s
- @mention in channel, verify thread response
- Post in general channel, verify probabilistic engagement
- Test all command types (post, remind, configure)
- Test error handling (invalid channel, permission denied)

---

## Example Event Flow (Full Stack)

**User Action**: "Hi Lukas, what's the weather?"

1. **Slack → Bot**: `message` event via Socket Mode
2. **Bot Handler**: `handle_message()` in `message_handler.py`
   - Extract channel, user, text
   - Load ConversationSession from DB (or create new)
   - Load last 10 message pairs for context
3. **LLM Service**: `generate_response()`
   - Build prompt with persona + context
   - Call any-llm API
   - Return generated response
4. **Bot → Slack**: Post message via `say()`
5. **DB Update**: Store user message + bot response in Messages table
6. **Logging**: Log event for monitoring

**Total Time**: <5s (target)
