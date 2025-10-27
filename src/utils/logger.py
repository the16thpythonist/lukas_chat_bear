"""
Logging configuration for Lukas the Bear chatbot.

Provides centralized logging setup with appropriate formatters and handlers.
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(
    name: str = "lukas_bear",
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return a logger instance.

    Args:
        name: Logger name (default: "lukas_bear")
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Falls back to LOG_LEVEL env var, then INFO
        log_file: Optional file path to write logs

    Returns:
        Configured logger instance
    """
    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger instance
logger = setup_logger()
