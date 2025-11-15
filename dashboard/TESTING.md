# Dashboard Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for the Lukas the Bear dashboard. The goal is to ensure all functionality works correctly and prevent regressions when making changes.

## Testing Philosophy

We follow the **Testing Pyramid** approach:

```
        /\
       /  \     E2E Tests (Few)
      /____\    - Full user workflows
     /      \   - Critical paths only
    /        \
   /__________\ Integration Tests (Some)
  /            \ - API endpoints
 /              \ - Database queries
/________________\ Unit Tests (Many)
                   - Individual functions
                   - Business logic
                   - Utilities
```

## Test Layers

### 1. Backend Unit Tests (`backend/tests/unit/`)

**What:** Test individual functions and classes in isolation with mocked dependencies.

**Coverage:**
- ✅ Query builders (filtering, pagination)
- ✅ Thumbnail generation logic
- ✅ Date formatting utilities
- ✅ Authentication helpers
- ✅ Error handlers

**Example:**
```python
def test_build_activity_query_with_date_filter():
    # Test that date filtering works correctly
    filters = {'start_date': '2025-01-01T00:00:00'}
    query = build_activity_query(mock_session, filters)
    # Assert query has correct WHERE clause
```

### 2. Backend Integration Tests (`backend/tests/integration/`)

**What:** Test full API endpoints with a real test database.

**Coverage:**
- ✅ Authentication flow (login, logout, session)
- ✅ Activity log API (GET /api/activity)
- ✅ Images API (GET /api/images, thumbnails)
- ✅ Events API (GET /api/events/upcoming, /api/events/completed)
- ✅ Pagination across all endpoints
- ✅ Error responses (404, 401, 500)

**Example:**
```python
def test_activity_api_with_pagination(client, auth_token):
    response = client.get('/api/activity?page=2&limit=10',
                         headers={'Authorization': f'Bearer {auth_token}'})
    assert response.status_code == 200
    assert len(response.json['items']) <= 10
    assert response.json['page'] == 2
```

### 3. Frontend Unit Tests (`frontend/tests/unit/`)

**What:** Test Vue components and utilities in isolation.

**Coverage:**
- ✅ Date formatting functions
- ✅ API service calls (mocked)
- ✅ Component rendering
- ✅ Event handlers
- ✅ Computed properties

**Example:**
```javascript
test('formatDateTime displays correct format', () => {
  const result = formatDateTime('2025-10-28T21:00:00')
  expect(result).toBe('10/28/2025, 21:00:47')
})
```

### 4. End-to-End Tests (`tests/e2e/`)

**What:** Test complete user workflows in a real browser.

**Coverage:**
- ✅ Login → View Activity → Logout
- ✅ View Images with filters
- ✅ View Scheduled Events
- ✅ Navigation between pages
- ✅ Error handling (network failures)

**Example:**
```javascript
test('user can view activity log', async ({ page }) => {
  await page.goto('http://localhost:5173')
  await page.fill('input[type="password"]', 'dev_password_123')
  await page.click('button[type="submit"]')
  await page.click('a:has-text("Activity")')
  await expect(page.locator('.activity-item')).toBeVisible()
})
```

## Test Data Strategy

### Test Database
- Use SQLite in-memory database for unit tests
- Use temporary file database for integration tests
- Seed with known data fixtures
- Clean up between tests

### Fixtures (`backend/tests/fixtures/`)
- `database.py`: Database session fixtures
- `test_data.py`: Sample messages, images, events
- `auth.py`: Authentication tokens

## Running Tests

### Backend Tests

```bash
# All backend tests
cd dashboard/backend
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage report
pytest --cov=backend --cov-report=html
```

### Frontend Tests

```bash
# All frontend tests
cd dashboard/frontend
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run E2E tests
cd dashboard
npm run test:e2e

# With UI
npm run test:e2e:ui
```

### All Tests (CI)

```bash
# Run everything
./run-all-tests.sh
```

## Coverage Goals

- **Backend:** Minimum 80% code coverage
- **Frontend:** Minimum 70% code coverage
- **Critical paths:** 100% coverage (auth, API endpoints)

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Dashboard Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r dashboard/backend/requirements.txt
      - name: Run tests
        run: pytest dashboard/backend/tests --cov

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: cd dashboard/frontend && npm ci
      - name: Run tests
        run: cd dashboard/frontend && npm run test

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E tests
        run: docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## Critical Test Scenarios

### Authentication
- ✅ Login with correct password
- ✅ Login with incorrect password
- ✅ Session persistence across page loads
- ✅ Logout clears session
- ✅ Protected routes redirect to login

### Activity Log
- ✅ Display messages correctly sorted
- ✅ Pagination works (next/previous)
- ✅ Date range filtering
- ✅ Recipient filtering
- ✅ Channel type filtering
- ✅ Empty state when no messages
- ✅ Error handling when API fails

### Images Gallery
- ✅ Display images with thumbnails
- ✅ Thumbnail generation for new images
- ✅ Placeholder for expired URLs
- ✅ Date filtering
- ✅ Status filtering (generated, posted, failed)
- ✅ Empty state
- ✅ Image detail view

### Scheduled Events
- ✅ Show upcoming events sorted correctly
- ✅ Show completed events with pagination
- ✅ Format metadata (intervals) properly
- ✅ Display countdown correctly
- ✅ Event icons display correctly
- ✅ Empty state for no events

### Error Handling
- ✅ 404 page for invalid routes
- ✅ API error messages displayed
- ✅ Network failure handling
- ✅ Invalid filter parameters
- ✅ Session expiry handling

## Test Maintenance

### When to Update Tests
- ✅ When adding new features → add corresponding tests
- ✅ When fixing bugs → add regression test
- ✅ When refactoring → ensure tests still pass
- ✅ When API changes → update integration tests

### Test Review Checklist
- [ ] Tests are independent (can run in any order)
- [ ] Tests clean up after themselves
- [ ] Tests are fast (< 1s for unit tests)
- [ ] Tests have clear names describing what they test
- [ ] Tests use fixtures instead of duplicating setup
- [ ] Mocks are used appropriately (not over-mocking)

## Tools & Dependencies

### Backend Testing
- `pytest` - Test framework
- `pytest-flask` - Flask testing helpers
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking helpers

### Frontend Testing
- `vitest` - Fast unit test runner
- `@vue/test-utils` - Vue component testing
- `playwright` - E2E testing
- `happy-dom` - DOM simulation

## Quick Start Guide

### Running Tests for the First Time

```bash
# 1. Install backend test dependencies
cd dashboard/backend
pip install -r requirements.txt

# 2. Run backend tests
pytest

# 3. Install frontend test dependencies
cd ../frontend
npm install

# 4. Run frontend tests
npm run test

# 5. See coverage reports
# Backend: open backend/htmlcov/index.html
# Frontend: open frontend/coverage/index.html
```

### Writing Your First Test

**Backend Unit Test:**
```python
# backend/tests/unit/test_query_builder.py
def test_paginate_returns_correct_page(test_session):
    # Setup: Create test data
    # Execute: Call paginate function
    # Assert: Check results match expectations
    pass
```

**Frontend Component Test:**
```javascript
// frontend/tests/unit/components/EventTimeline.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EventTimeline from '@/components/EventTimeline.vue'

describe('EventTimeline', () => {
  it('renders events correctly', () => {
    const wrapper = mount(EventTimeline, {
      props: { events: mockEvents }
    })
    expect(wrapper.find('.timeline-item')).toBeTruthy()
  })
})
```

## Future Enhancements

- [ ] Visual regression testing (screenshots)
- [ ] Performance testing (load times)
- [ ] Accessibility testing (a11y)
- [ ] Security testing (OWASP top 10)
- [ ] Load testing (concurrent users)
