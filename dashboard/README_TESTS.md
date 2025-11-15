# Dashboard Testing Guide

Quick reference for running dashboard tests.

## Quick Start

### Run All Tests

```bash
./run-tests.sh
```

### Run with Coverage

```bash
./run-tests.sh --coverage
```

### Backend Tests Only

```bash
./run-tests.sh --backend-only
```

### Unit Tests Only

```bash
./run-tests.sh --unit
```

## Backend Testing

### Run All Backend Tests

```bash
cd dashboard/backend
pytest
```

### Run Specific Test File

```bash
pytest tests/unit/test_query_builder.py
```

### Run Specific Test

```bash
pytest tests/unit/test_query_builder.py::TestPagination::test_paginate_first_page
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=backend --cov-report=html
# View report at: backend/htmlcov/index.html
```

### Run Only Integration Tests

```bash
pytest tests/integration/
```

## Frontend Testing

### Run All Frontend Tests

```bash
cd dashboard/frontend
npm run test
```

### Run in Watch Mode

```bash
npm run test:watch
```

### Run with Coverage

```bash
npm run test:coverage
# View report at: frontend/coverage/index.html
```

## Test Structure

```
dashboard/
├── backend/tests/
│   ├── conftest.py          # Shared fixtures
│   ├── unit/                # Unit tests
│   │   └── test_query_builder.py
│   └── integration/         # API integration tests
│       └── test_events_api.py
└── frontend/tests/          # Frontend tests (to be added)
    ├── unit/
    └── e2e/
```

## Writing New Tests

### Backend Unit Test Example

```python
# tests/unit/test_my_feature.py
def test_my_function(db_session, sample_data):
    """Test description."""
    result = my_function(sample_data)
    assert result == expected_value
```

### Backend Integration Test Example

```python
# tests/integration/test_my_api.py
def test_my_endpoint(authenticated_client):
    """Test API endpoint."""
    response = authenticated_client.get('/api/my-endpoint')
    assert response.status_code == 200
    assert 'data' in response.get_json()
```

## Available Fixtures

- `app` - Flask app instance
- `client` - Test client (not authenticated)
- `authenticated_client` - Test client with valid session
- `db_session` - Database session with clean state
- `sample_team_members` - 3 test team members
- `sample_conversations` - 2 test conversations
- `sample_messages` - 20 test messages
- `sample_images` - 10 test images
- `sample_scheduled_tasks` - 8 test tasks (3 upcoming, 5 completed)

## Continuous Integration

### GitHub Actions

The tests run automatically on:
- Push to any branch
- Pull request creation
- Pull request updates

### Running Tests in Docker

```bash
# Build test container
docker-compose -f docker-compose.test.yml build

# Run tests
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Coverage Goals

- **Backend:** Minimum 80% coverage
- **Critical paths:** 100% coverage (auth, core APIs)
- **Frontend:** Minimum 70% coverage

## Troubleshooting

### "ModuleNotFoundError" when running tests

```bash
# Install backend dependencies
cd dashboard/backend
pip install -r requirements.txt
```

### "Cannot find module" in frontend tests

```bash
# Install frontend dependencies
cd dashboard/frontend
npm install
```

### Tests fail with database errors

- Make sure you're using a clean database session
- Check that fixtures are properly imported
- Verify models are imported in test files

### Test timeouts

- Increase timeout with `pytest --timeout=30`
- Check for infinite loops in test code
- Ensure mock objects are properly configured

## Best Practices

1. **Keep tests independent** - Tests should not depend on each other
2. **Use fixtures** - Don't duplicate setup code
3. **Test one thing** - Each test should verify one behavior
4. **Clear names** - Test names should describe what they test
5. **Fast tests** - Unit tests should run in < 1 second
6. **Clean up** - Tests should clean up after themselves

## Resources

- Full testing strategy: See `TESTING.md`
- pytest documentation: https://docs.pytest.org/
- Flask testing: https://flask.palletsprojects.com/en/latest/testing/
- Vitest: https://vitest.dev/
- Vue Test Utils: https://test-utils.vuejs.org/
