"""
Bot Service Invoker - HTTP Client Version

This module communicates with the bot container's internal API via HTTP.
No direct imports of bot services - all communication is through HTTP requests.

Architecture:
- Dashboard container makes HTTP requests to bot container
- Bot container runs internal Flask API (port 5001)
- Communication over Docker internal network only
- No shared dependencies (dashboard doesn't need OpenAI, Slack, etc.)

Usage:
    from services.bot_invoker import invoke_image_generation, invoke_random_dm

    result = invoke_image_generation(theme="celebration", channel_id="C123456")
    if result['success']:
        print(f"Image generated: {result['image_id']}")
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import json
import os

# HTTP client for API calls
import requests

# Import database session management for audit logging
from .database import session_scope

logger = logging.getLogger(__name__)

# Bot API URL from environment (Docker network)
# Default: http://lukas-bear-bot-dev:5001 for development
# Production: http://lukas-bear-bot:5001
BOT_API_URL = os.getenv('BOT_API_URL', 'http://lukas-bear-bot-dev:5001')

# HTTP timeout settings
API_TIMEOUT_GENERATE_IMAGE = 120  # DALL-E can be slow (2 minutes)
API_TIMEOUT_SEND_DM = 30  # DM sending should be faster (30 seconds)
API_TIMEOUT_HEALTH = 5  # Health check should be quick (5 seconds)


def check_bot_api_health() -> bool:
    """
    Check if bot internal API is reachable and healthy.

    Returns:
        bool: True if API is healthy, False otherwise
    """
    try:
        response = requests.get(
            f'{BOT_API_URL}/api/internal/health',
            timeout=API_TIMEOUT_HEALTH
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('services_initialized', False)
        return False
    except Exception as e:
        logger.error(f"Bot API health check failed: {e}")
        return False


def invoke_image_generation(
    theme: Optional[str] = None,
    channel_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke bot's image generation service via HTTP API.

    This function:
    1. Makes HTTP POST to bot container's internal API
    2. Returns success/failure with user-friendly messages
    3. Logs action to scheduled_tasks (done by bot API)

    Args:
        theme: Optional theme for image generation (e.g., "celebration", "nature")
        channel_id: Optional target channel ID. If None, uses default from config.

    Returns:
        Dict with keys:
            - success (bool): Whether operation succeeded
            - message (str): User-friendly message
            - image_id (int): Generated image ID (if success)
            - error (str): Error details (if failure)

    Example:
        >>> result = invoke_image_generation(theme="winter", channel_id="C123456")
        >>> if result['success']:
        ...     print(f"Image {result['image_id']} posted successfully")
    """
    try:
        logger.info(f"Calling bot API: generate-image (theme={theme}, channel={channel_id})")

        # Make HTTP request to bot internal API
        response = requests.post(
            f'{BOT_API_URL}/api/internal/generate-image',
            json={
                'theme': theme,
                'channel_id': channel_id
            },
            timeout=API_TIMEOUT_GENERATE_IMAGE
        )

        # Parse response
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Image generated successfully via bot API: ID={data.get('image_id')}")

            return {
                'success': True,
                'message': f'Image generated and posted successfully to channel {channel_id or "default"}',
                'image_id': data.get('image_id'),
                'image_url': data.get('image_url'),
                'prompt': data.get('prompt')
            }
        else:
            # API returned error
            try:
                error_data = response.json()
                error_message = error_data.get('error', 'Unknown error')
            except:
                error_message = response.text or 'Unknown error'

            logger.error(f"Bot API returned error: {response.status_code} - {error_message}")

            return {
                'success': False,
                'message': _translate_error_message(error_message),
                'error': error_message
            }

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Bot API connection failed: {e}")
        return {
            'success': False,
            'message': 'Bot service unavailable - cannot connect to bot container. Please check if bot is running.',
            'error': 'Connection refused'
        }

    except requests.exceptions.Timeout as e:
        logger.error(f"Bot API timeout: {e}")
        return {
            'success': False,
            'message': 'Bot service timeout - image generation took too long (>2 minutes). Please try again.',
            'error': 'Request timeout'
        }

    except Exception as e:
        logger.error(f"Bot API call failed: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Failed to communicate with bot service: {str(e)}',
            'error': str(e)
        }


def invoke_random_dm(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Invoke bot's proactive DM service via HTTP API.

    This function:
    1. Makes HTTP POST to bot container's internal API
    2. Returns success/failure with user-friendly messages
    3. Logs action to scheduled_tasks (done by bot API)

    Args:
        user_id: Optional target user Slack ID. If None, selects random user.

    Returns:
        Dict with keys:
            - success (bool): Whether operation succeeded
            - message (str): User-friendly message
            - target_user (str): Recipient user ID
            - dm_content (str): Message content preview (if success)
            - error (str): Error details (if failure)

    Example:
        >>> result = invoke_random_dm(user_id="U123456")
        >>> if result['success']:
        ...     print(f"DM sent to {result['target_user']}")
    """
    try:
        logger.info(f"Calling bot API: send-dm (user_id={user_id or 'random'})")

        # Make HTTP request to bot internal API
        response = requests.post(
            f'{BOT_API_URL}/api/internal/send-dm',
            json={'user_id': user_id},
            timeout=API_TIMEOUT_SEND_DM
        )

        # Parse response
        if response.status_code == 200:
            data = response.json()
            target_user = data.get('target_user', 'unknown')

            logger.info(f"DM sent successfully via bot API to {target_user}")

            return {
                'success': True,
                'message': f'Random DM sent successfully to user {target_user}',
                'target_user': target_user,
                'dm_content': data.get('message_preview', '(no preview available)')
            }
        else:
            # API returned error
            try:
                error_data = response.json()
                error_message = error_data.get('error', 'Unknown error')
            except:
                error_message = response.text or 'Unknown error'

            logger.error(f"Bot API returned error: {response.status_code} - {error_message}")

            return {
                'success': False,
                'message': _translate_error_message(error_message),
                'error': error_message
            }

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Bot API connection failed: {e}")
        return {
            'success': False,
            'message': 'Bot service unavailable - cannot connect to bot container. Please check if bot is running.',
            'error': 'Connection refused'
        }

    except requests.exceptions.Timeout as e:
        logger.error(f"Bot API timeout: {e}")
        return {
            'success': False,
            'message': 'Bot service timeout - DM sending took too long (>30 seconds). Please try again.',
            'error': 'Request timeout'
        }

    except Exception as e:
        logger.error(f"Bot API call failed: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Failed to communicate with bot service: {str(e)}',
            'error': str(e)
        }


def invoke_bot_internal_api(
    method: str,
    endpoint: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Generic function to invoke any bot internal API endpoint.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path (e.g., '/api/internal/scheduled-events')
        json: Optional JSON body for request
        params: Optional query parameters
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dict: Response data from API

    Raises:
        Exception: If API call fails
    """
    try:
        url = f'{BOT_API_URL}{endpoint}'
        logger.info(f"Calling bot API: {method} {endpoint}")

        # Make HTTP request
        response = requests.request(
            method=method.upper(),
            url=url,
            json=json,
            params=params,
            timeout=timeout
        )

        # Parse response
        try:
            data = response.json()
        except:
            data = {'error': response.text or 'Unknown error'}

        # Check if successful
        if response.status_code in [200, 201]:
            logger.info(f"Bot API call successful: {method} {endpoint}")
            return data
        else:
            # API returned error
            error_message = data.get('error', 'Unknown error')
            logger.error(f"Bot API returned error: {response.status_code} - {error_message}")
            raise Exception(error_message)

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Bot API connection failed: {e}")
        raise Exception('Bot service unavailable - cannot connect to bot container')

    except requests.exceptions.Timeout as e:
        logger.error(f"Bot API timeout: {e}")
        raise Exception(f'Bot service timeout - request took too long (>{timeout}s)')

    except Exception as e:
        if 'Bot service' not in str(e):
            logger.error(f"Bot API call failed: {e}", exc_info=True)
        raise


def _translate_error_message(error: str) -> str:
    """
    Translate technical error messages to user-friendly messages.

    Args:
        error: Raw error message from bot API

    Returns:
        User-friendly error message
    """
    error_lower = error.lower()

    # Check for specific error patterns
    if 'openai' in error_lower or 'api key' in error_lower:
        return 'OpenAI API key not configured or invalid - please check bot configuration'
    elif 'rate limit' in error_lower:
        return 'OpenAI API rate limit exceeded - please try again later (cooldown period)'
    elif 'slack' in error_lower and 'channel' in error_lower:
        return f'Failed to post to Slack channel - please check channel ID'
    elif 'timeout' in error_lower:
        return 'Request timed out - external API may be slow. Please try again.'
    elif 'no active users' in error_lower or 'no users' in error_lower:
        return 'No active team members available to send DM'
    elif 'connection' in error_lower or 'refused' in error_lower:
        return 'Cannot connect to Slack or external services - please check network'
    else:
        # Return original error if no specific pattern matches
        return f'Operation failed: {error}'
