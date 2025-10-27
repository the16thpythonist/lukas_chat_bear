# LLM Service API Contracts

**Purpose**: Define interfaces for any-llm integration and OpenAI DALL-E

---

## any-llm Chat API

### Overview

`any-llm` (https://github.com/mozilla-ai/any-llm) is a Mozilla AI Python library providing a unified interface to multiple LLM providers (OpenAI, Anthropic, Cohere, HuggingFace, local models). We use its chat completion interface with conversation history.

### Base Configuration

**Library**: `any-llm` Python package
**Installation**: `pip install any-llm`
**Providers**: Configured via environment variables or config
**Model**: Specified per-provider (e.g., GPT-3.5-turbo, Claude, Cohere Command, local models)

---

### 1. Chat Completion Request

**Python API**: Function call (not HTTP)
**Installation**: `pip install 'any-llm-sdk[openai]'` (install with desired provider)

**Two Approaches**:

#### Approach 1: Class-Based (Recommended for Production)

```python
from any_llm import AnyLLM

# Initialize client once, reuse for multiple requests
llm = AnyLLM.create(
    provider="openai",
    api_key=os.environ["OPENAI_API_KEY"]
)

# Build message history
messages = [
    {
        "role": "system",
        "content": "You are Lukas the Bear, a friendly stuffed animal mascot of the research team..."
    },
    {
        "role": "user",
        "content": "Hi Lukas, how are you?"
    },
    {
        "role": "assistant",
        "content": "Hey there! I'm doing great, thanks! 🐻"
    },
    {
        "role": "user",
        "content": "What's the weather like today?"
    }
]

# Get completion
response = llm.completion(
    model="gpt-3.5-turbo",
    messages=messages,
    temperature=0.7,
    max_tokens=150
)
```

#### Approach 2: Direct Function (Simple)

```python
from any_llm import completion

# Direct call without creating client instance
response = completion(
    model="openai:gpt-3.5-turbo",  # provider:model format
    messages=messages,
    temperature=0.7,
    max_tokens=150
)
# Note: Creates new client each time, less efficient for multiple calls
```

**Parameters**:
- `model` (string, required): Model name (provider:model format or just model if provider specified separately)
- `messages` (list, required): Conversation history with roles
  - Limited to last 10 message pairs (20 messages total)
  - Includes system prompt as first message
  - Roles: "system", "user", "assistant"
- `provider` (string, conditional): Provider name if not in model string (e.g., "openai", "anthropic", "mistral", "ollama")
- `api_key` (string, optional): Provider API key (defaults to environment variable)
- `temperature` (float, optional): Creativity level (0.0-1.0)
- `max_tokens` (int, optional): Maximum response length
- `stream` (bool, optional): Enable streaming responses

---

### 2. Chat Completion Response

**Success Response** (Python object):
```python
# Response is a ChatCompletion object
response = client.create(messages=messages)

# Access the generated text
assistant_message = response.choices[0].message.content
# "The weather today is lovely! Perfect day for a bear to be outside. How about you - any plans to enjoy this beautiful day? 🐻☀️"

# Full response structure (similar to OpenAI format):
{
    "id": "chatcmpl-xyz123",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "gpt-3.5-turbo",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "The weather today is lovely! Perfect day for a bear to be outside..."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 45,
        "completion_tokens": 28,
        "total_tokens": 73
    }
}
```

**Field Descriptions**:
- `choices[0].message.content` (string): Generated response from LLM
- `usage` (dict): Token usage for cost tracking
- `finish_reason` (string): "stop" (complete), "length" (hit max_tokens), "content_filter" (filtered)

**Error Response** (Exception raised):
```python
try:
    response = client.create(messages=messages)
except Exception as e:
    # Provider-specific exceptions wrapped by any-llm
    # OpenAI: openai.AuthenticationError, openai.RateLimitError, etc.
    # Anthropic: anthropic.AuthenticationError, etc.
    # Generic: any_llm.APIError
    pass
```

---

### 3. Error Handling

**Exception Types** (any-llm wraps provider-specific errors):

| Exception | Meaning | Bot Behavior |
|-----------|---------|--------------|
| Success | No exception raised | Return response.choices[0].message.content to user |
| `ValueError` | Invalid parameters (bad messages format) | Log error, return fallback: "I'm having trouble understanding that..." |
| `AuthenticationError` | Invalid API key for provider | Log critical error, return fallback, alert admin |
| `RateLimitError` | Provider rate limit exceeded | Retry with exponential backoff (3 attempts), then fallback |
| `APIError` | Provider server error | Retry with exponential backoff, then fallback |
| `TimeoutError` | Request timeout | Retry with backoff, then fallback |
| `Exception` | Generic error | Log and return fallback |

**Fallback Responses** (when LLM unavailable):
```python
FALLBACK_RESPONSES = [
    "I'm feeling a bit fuzzy right now 🐻 Can you try again in a moment?",
    "My bear brain needs a quick nap! Give me a second to wake up...",
    "Oops, I'm having trouble thinking clearly. Mind trying that again?",
]
```

Pick random fallback to avoid repetition.

**Provider Configuration** (environment variables):
```python
# Configure provider in config.yml or environment
LLM_PROVIDER = "openai"  # or "anthropic", "cohere", "huggingface"
LLM_MODEL = "gpt-3.5-turbo"  # Provider-specific model name
LLM_API_KEY = os.environ.get(f"{LLM_PROVIDER.upper()}_API_KEY")

# any-llm handles provider-specific differences transparently
```

---

### 4. Retry Policy

**Configuration**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from any_llm import AnyLLM

# Initialize client once for the application
llm = AnyLLM.create(provider="openai", api_key=os.environ["OPENAI_API_KEY"])

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry_if_exception_type=(TimeoutError, Exception),  # Catch provider errors
    reraise=True
)
def chat_completion(messages):
    """
    Call any-llm with retry logic.
    any-llm uses official provider SDKs, so errors are provider-specific.
    """
    response = llm.completion(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
        max_tokens=150
    )
    return response.choices[0].message.content
```

**Retry Conditions**:
- Network timeouts
- Rate limit errors (provider-specific)
- Server errors (provider-specific)

**Do NOT Retry**:
- `ValueError` (bad parameters) - indicates code bug
- `AuthenticationError` (auth failure) - needs admin intervention

---

### 5. Context Management

**System Prompt** (always first in chatHistory):
```text
You are Lukas the Bear, a stuffed animal and beloved mascot of a research team. You have a warm, friendly, and slightly playful personality. You're helpful and supportive, but also enjoy light-hearted banter.

Key personality traits:
- Warm and encouraging (like a teddy bear should be!)
- Occasionally mentions honey or bear-related topics
- Uses 🐻 emoji naturally but not excessively
- Professional but friendly - appropriate for workplace
- Curious about team members' work and well-being
- Remembers context from conversation history

Guidelines:
- Keep responses concise (2-4 sentences usually)
- Be genuinely helpful when asked questions
- Use team member's name when you know it
- Maintain consistency with previous messages in conversation
- If you don't know something, admit it honestly
- Avoid controversial topics or anything inappropriate for work

You're part of a research team, so be supportive of their work and interested in their projects.
```

**Conversation History Format**:
```python
def build_chat_history(conversation_session):
    """
    Build chat history from last N message pairs.

    Returns:
        List of message dictionaries for any-llm API
    """
    messages = [
        {"role": "system", "content": PERSONA_SYSTEM_PROMPT}
    ]

    # Get last 10 message pairs (20 messages) from DB
    recent_messages = (
        session.query(Message)
        .filter(Message.conversation_id == conversation_session.id)
        .order_by(Message.timestamp.desc())
        .limit(20)
        .all()
    )

    # Reverse to chronological order
    recent_messages.reverse()

    for msg in recent_messages:
        role = "assistant" if msg.sender_type == "bot" else "user"
        messages.append({
            "role": role,
            "content": msg.content
        })

    return messages
```

**Token Estimation**:
```python
import tiktoken

def estimate_tokens(messages):
    """
    Estimate token count for message history.
    Uses cl100k_base encoding (GPT-3.5/GPT-4 tokenizer).
    """
    enc = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0

    for msg in messages:
        total_tokens += len(enc.encode(msg["content"]))
        total_tokens += 4  # Role tokens

    return total_tokens

# Truncate if exceeds limit
MAX_TOKENS = 4000
if estimate_tokens(messages) > MAX_TOKENS:
    # Remove oldest user/assistant pairs until under limit
    while estimate_tokens(messages) > MAX_TOKENS and len(messages) > 3:
        messages.pop(1)  # Keep system prompt (index 0)
        if len(messages) > 1:
            messages.pop(1)  # Remove corresponding response
```

---

## OpenAI DALL-E Image Generation API

### Overview

Generate bear-themed images using DALL-E 3 for periodic posting to Slack.

### Base Configuration

**Endpoint**: `https://api.openai.com/v1/images/generations`
**Authentication**: Bearer token in header
**Model**: DALL-E 3

---

### 1. Image Generation Request

**HTTP Method**: POST
**Path**: `/v1/images/generations`
**Headers**:
```json
{
  "Authorization": "Bearer {OPENAI_API_KEY}",
  "Content-Type": "application/json"
}
```

**Request Body**:
```json
{
  "model": "dall-e-3",
  "prompt": "A friendly stuffed teddy bear mascot enjoying a beautiful autumn day, surrounded by colorful fall leaves, warm lighting, whimsical art style",
  "n": 1,
  "size": "1024x1024",
  "quality": "standard",
  "style": "natural"
}
```

**Field Descriptions**:
- `model` (string): Always "dall-e-3"
- `prompt` (string): Detailed image description (max 4000 chars)
- `n` (integer): Number of images (always 1)
- `size` (string): "1024x1024" (standard DALL-E 3 size)
- `quality` (string): "standard" or "hd" (use standard to save cost)
- `style` (string): "natural" or "vivid" (natural fits bear persona better)

---

### 2. Image Generation Response

**Success Response** (200 OK):
```json
{
  "created": 1698765432,
  "data": [
    {
      "url": "https://oaidalleapiprodscus.blob.core.windows.net/private/...",
      "revised_prompt": "A friendly stuffed teddy bear mascot in an autumn setting..."
    }
  ]
}
```

**Field Descriptions**:
- `created` (unix timestamp): Generation time
- `data[].url` (string): Temporary URL to image (expires in 60 days)
- `data[].revised_prompt` (string): DALL-E's interpretation of prompt

**Error Response** (4xx/5xx):
```json
{
  "error": {
    "message": "Your request was rejected as a result of our safety system",
    "type": "invalid_request_error",
    "code": "content_policy_violation"
  }
}
```

---

### 3. Prompt Templates

**Prompt Generation Strategy**:
```python
def generate_image_prompt(theme=None, occasion=None):
    """
    Generate contextual DALL-E prompt for bear image.

    Args:
        theme: Season or topic (e.g., "autumn", "winter", "science")
        occasion: Special event (e.g., "halloween", "holiday", "team milestone")

    Returns:
        String prompt for DALL-E
    """
    base = "A friendly stuffed teddy bear mascot named Lukas"

    # Theme-specific modifiers
    themes = {
        "autumn": "surrounded by colorful fall leaves, warm golden lighting",
        "winter": "in a cozy winter scene with snow, wearing a scarf",
        "spring": "among blooming flowers, bright cheerful colors",
        "summer": "enjoying sunshine, picnic setting",
        "science": "in a research lab, surrounded by beakers and books",
        "celebration": "holding balloons, confetti, festive atmosphere"
    }

    # Occasion-specific additions
    occasions = {
        "halloween": "with friendly jack-o-lanterns, autumn decorations",
        "thanksgiving": "with a pie and grateful expression",
        "holiday": "with wrapped presents and holiday lights",
        "milestone": "giving a thumbs up, achievement celebration"
    }

    prompt_parts = [base]

    if theme and theme in themes:
        prompt_parts.append(themes[theme])

    if occasion and occasion in occasions:
        prompt_parts.append(occasions[occasion])

    # Standard quality modifiers
    prompt_parts.extend([
        "whimsical illustration style",
        "warm and inviting atmosphere",
        "family-friendly",
        "high quality digital art"
    ])

    return ", ".join(prompt_parts)
```

**Example Generated Prompts**:

1. Default (no theme):
   ```
   A friendly stuffed teddy bear mascot named Lukas, whimsical illustration style, warm and inviting atmosphere, family-friendly, high quality digital art
   ```

2. Autumn theme:
   ```
   A friendly stuffed teddy bear mascot named Lukas, surrounded by colorful fall leaves, warm golden lighting, whimsical illustration style, warm and inviting atmosphere, family-friendly, high quality digital art
   ```

3. Holiday occasion:
   ```
   A friendly stuffed teddy bear mascot named Lukas, with wrapped presents and holiday lights, whimsical illustration style, warm and inviting atmosphere, family-friendly, high quality digital art
   ```

---

### 4. Content Safety

**OpenAI Safety System**:
- Automatic content moderation
- Rejects prompts violating content policy
- Blocks generation of inappropriate images

**Our Additional Checks**:
```python
def validate_prompt(prompt):
    """
    Pre-validate prompt before sending to DALL-E.
    """
    # Block prompts with banned words/phrases
    banned_terms = [...]  # Define internally

    prompt_lower = prompt.lower()
    for term in banned_terms:
        if term in prompt_lower:
            raise ValueError(f"Prompt contains inappropriate term")

    # Length check
    if len(prompt) > 4000:
        raise ValueError("Prompt exceeds 4000 character limit")

    return True
```

**Handling Content Violations**:
```python
try:
    response = generate_image(prompt)
except openai.BadRequestError as e:
    if "content_policy_violation" in str(e):
        # Log for review, don't retry, skip this image post
        logger.error(f"Prompt rejected by OpenAI safety: {prompt}")
        # Store in GeneratedImage with status='failed'
        return None
```

---

### 5. Cost Tracking

**DALL-E 3 Pricing** (as of 2024):
- Standard quality, 1024x1024: $0.040/image
- HD quality, 1024x1024: $0.080/image

**Usage Estimates**:
- 1 image/week = ~52 images/year
- Annual cost (standard): $2.08
- Monthly cost (standard): ~$0.17

**Cost Logging**:
```python
def log_image_cost(size, quality):
    """
    Calculate and log cost for generated image.
    """
    costs = {
        ("1024x1024", "standard"): 0.040,
        ("1024x1024", "hd"): 0.080,
    }

    cost_usd = costs.get((size, quality), 0.040)

    # Store in GeneratedImage.cost_usd
    return cost_usd
```

---

### 6. Error Handling & Retries

**Retry Policy**:
```python
@retry(
    stop=stop_after_attempt(2),  # Only 2 attempts for images
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry_if_exception_type=(openai.RateLimitError, openai.APIConnectionError),
    reraise=True
)
def generate_image(prompt):
    """
    Generate image with limited retries.
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="standard"
    )

    return response.data[0].url
```

**Error Scenarios**:

| Error | Retry | Action |
|-------|-------|--------|
| Rate limit (429) | Yes (2x) | Wait and retry, then fail gracefully |
| Content violation (400) | No | Log and skip this image |
| Network timeout | Yes (2x) | Retry with backoff |
| Auth failure (401) | No | Log critical error, alert admin |
| Server error (500) | Yes (2x) | Retry, then skip |

**Graceful Failure**:
- If image generation fails, log to GeneratedImage table with status='failed'
- Don't block other bot functions
- Schedule next attempt for next interval (don't retry immediately)

---

### 7. Image Download & Caching

**URL Expiration**:
- DALL-E URLs expire after 60 days
- For long-term storage, download image and host separately

**Download Implementation** (Phase 2 - out of scope for MVP):
```python
import httpx

async def download_image(url):
    """
    Download generated image from DALL-E URL.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

# Save to local storage or S3
def save_image(image_data, filename):
    """Save image bytes to persistent storage."""
    path = f"/app/data/images/{filename}"
    with open(path, "wb") as f:
        f.write(image_data)
    return path
```

**MVP Approach**:
- Store DALL-E URL directly
- Use URL for Slack posting (Slack caches images)
- Accept that images may become unavailable after 60 days
- Database retains prompt for regeneration if needed

---

## Testing Contracts

### LLM Service Mock

```python
from unittest.mock import Mock

class MockAnyLLM:
    """Mock any-llm for testing."""

    def completion(self, model, messages, **kwargs):
        """Return canned response for testing."""
        # Return OpenAI-compatible response format
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hey there! I'm doing great, thanks! 🐻"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 50
        return mock_response
```

### Image Generation Mock

```python
class MockDallE:
    """Mock DALL-E for testing."""

    def generate(self, prompt, **kwargs):
        """Return test image URL."""
        return {
            "data": [{
                "url": "https://test.example.com/bear.png",
                "revised_prompt": prompt
            }]
        }
```

### Integration Test Strategy

1. **Staging Environment**:
   - Real any-llm with OpenAI provider (or test provider)
   - Separate API key for testing (track test costs)
   - Consider using local providers (ollama) for testing to avoid API costs

2. **Test Scenarios**:
   - Generate response with empty history
   - Generate response with full context (10 pairs)
   - Switch providers (test with multiple providers if configured)
   - Generate image with various themes
   - Handle API errors (mock failures)

3. **Cost Control**:
   - Use GPT-3.5-turbo for testing (cheaper than GPT-4)
   - Alternative: Use local ollama models for free testing
   - Limit image generation tests (pre-generate test images)
   - Monitor monthly test API costs

4. **Provider Flexibility Testing**:
   ```python
   # Test that bot works with different providers
   providers_to_test = ["openai", "anthropic", "mistral"]
   for provider in providers_to_test:
       if has_api_key(provider):
           test_conversation_with_provider(provider)
   ```

---

## Circuit Breaker Configuration

**Pattern**: Prevent cascading failures when LLM/image APIs down

```python
from pybreaker import CircuitBreaker

llm_breaker = CircuitBreaker(
    fail_max=5,          # Open after 5 consecutive failures
    timeout_duration=60,  # Stay open for 60 seconds
    exclude=[AuthError]  # Don't count auth errors (need admin fix)
)

@llm_breaker
def call_any_llm(message, history):
    """LLM call protected by circuit breaker."""
    # Implementation

# When circuit opens (too many failures):
# - Future calls raise CircuitBreakerError immediately
# - Return fallback responses without hitting API
# - After timeout, allow single test request
# - If succeeds, close circuit; if fails, re-open
```

**Benefits**:
- Prevents wasting time on known-down services
- Faster fallback responses
- Allows automatic recovery when service returns

---

## Next Steps

After contract approval, proceed to:
1. Quickstart Guide - Setup and configuration documentation
2. Implementation Tasks - Break down contracts into coding tasks
