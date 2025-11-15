# Changelog

All notable changes to Lukas the Bear Slack Chatbot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup and structure
- Slack Bolt SDK integration with Socket Mode
- SQLAlchemy database models for conversation tracking
- Alembic migrations for database schema management
- Configuration management (YAML + environment variables)
- Logging infrastructure
- **Scheduled Channel Messages**: Schedule one-time messages to be posted to Slack channels at future times
  - Natural language time parsing using dateparser (e.g., "3pm Friday", "in 2 hours", "tomorrow at 2pm")
  - Admin-only via Slack chat (using MCP tool `schedule_channel_message`)
  - Dashboard UI for creating, editing, viewing, and cancelling scheduled events
  - Status tracking: pending, completed, cancelled, failed
  - APScheduler integration with automatic job restoration on bot restart
  - REST API endpoints for scheduled events management (GET, POST, PUT, DELETE)
  - Database migration for `scheduled_events` table
  - Comprehensive unit tests for ScheduledEventService (31 tests, 85% coverage)

### Planned
- Direct conversation feature (User Story 1)
- Proactive team engagement (User Story 2)
- AI-generated image posting (User Story 3)
- Command execution (User Story 4)

## [0.1.0] - TBD

### Added
- Project initialization
- Docker Compose deployment setup
- Configuration templates
- Documentation (README, Quickstart, Technical Specs)

---

## Version History Guide

### Version Number Format: MAJOR.MINOR.PATCH

- **MAJOR**: Incompatible API changes or major feature overhauls
- **MINOR**: New features added in a backwards-compatible manner
- **PATCH**: Backwards-compatible bug fixes

### Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes
