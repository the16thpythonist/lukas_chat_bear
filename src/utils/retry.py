"""
Retry utilities with exponential backoff.

Provides decorators and utilities for retrying operations with tenacity.
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

from src.utils.logger import logger


def retry_on_api_error(max_attempts: int = 3, min_wait: int = 1, max_wait: int = 10):
    """
    Decorator for retrying API calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds

    Returns:
        Tenacity retry decorator

    Example:
        @retry_on_api_error(max_attempts=3)
        def call_llm_api():
            # API call code
            pass
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_on_connection_error(max_attempts: int = 3):
    """
    Decorator for retrying on connection errors.

    Args:
        max_attempts: Maximum number of retry attempts

    Returns:
        Tenacity retry decorator

    Example:
        @retry_on_connection_error()
        def connect_to_service():
            # Connection code
            pass
    """
    from requests.exceptions import ConnectionError, Timeout

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
