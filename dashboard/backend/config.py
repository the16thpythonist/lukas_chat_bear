"""
Configuration module for dashboard backend.
Loads environment variables and provides application configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class."""

    # Dashboard authentication
    DASHBOARD_ADMIN_PASSWORD = os.getenv('DASHBOARD_ADMIN_PASSWORD')
    if not DASHBOARD_ADMIN_PASSWORD:
        raise ValueError(
            "DASHBOARD_ADMIN_PASSWORD environment variable is required. "
            "Please set it in your .env file with a secure password (min 12 characters)."
        )

    # Warn if password is weak
    if len(DASHBOARD_ADMIN_PASSWORD) < 12:
        print(
            "⚠️  WARNING: DASHBOARD_ADMIN_PASSWORD is less than 12 characters. "
            "Consider using a stronger password for better security."
        )

    # Database configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/bot.db')
    DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_DIR = os.getenv('SESSION_DIR', '/app/sessions')
    SESSION_PERMANENT = False  # Session expires when browser closes
    SESSION_USE_SIGNER = True  # Sign session cookies for security
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to cookies
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    # Allow override via SESSION_COOKIE_SECURE env var (set to 'false' for HTTP access)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'

    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())

    # CORS configuration
    # Allow both development (Vite) and production (same-origin) requests
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:8080').split(',')
    CORS_SUPPORTS_CREDENTIALS = True

    # Rate limiting configuration
    RATE_LIMIT_MANUAL_CONTROLS = 10  # Max 10 manual controls per hour per session
    RATE_LIMIT_GENERAL_API = 100  # Max 100 requests per minute per IP

    # Thumbnail configuration
    THUMBNAIL_DIR = os.getenv('THUMBNAIL_DIR', '/app/thumbnails')
    THUMBNAIL_SIZE = (300, 300)
    THUMBNAIL_QUALITY = 85

    # Flask environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = FLASK_ENV == 'development'

    # Slack OAuth configuration
    SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID')
    SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET')
    SLACK_REDIRECT_URI = os.getenv('SLACK_REDIRECT_URI')  # Optional

    # OAuth tokens output directory
    OAUTH_TOKENS_DIR = os.getenv('OAUTH_TOKENS_DIR', '/app/data/oauth_tokens')

    # Warn if OAuth credentials are not configured
    if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
        print(
            "⚠️  WARNING: Slack OAuth credentials not configured. "
            "Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET to enable OAuth installation endpoint."
        )


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # SESSION_COOKIE_SECURE inherited from Config (can be overridden via env var)


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}


def get_config():
    """Get configuration based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'production')
    return config.get(env, config['default'])
