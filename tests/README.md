# Test Suite

This directory contains comprehensive tests for the Meeting Transcript Summarizer application.

## Running Tests

### Run all tests with coverage:
```bash
python run_tests.py
```

### Run tests manually:
```bash
pytest tests/ -v
```

### Run with coverage report:
```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing
```

### Run specific test file:
```bash
pytest tests/backend/models/test_schemas.py -v
```

### View HTML ccoverage report:
```bash
open htmlcov/index.html
```

## Test Coverage

The test suite aims for **80%+ code coverage**. Current coverage includes:

- ✅ **Models** (100%): All data models fully tested
- ✅ **Schemas** (100%): All API schemas tested
- ✅ **Storage** (91%): Database operations tested
- ✅ **API Endpoints** (72-90%): Most endpoints tested
- ✅ **Core Modules**: Core functionality tested

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── backend/
│   ├── models/                   # API schema tests
│   ├── meeting_summarizer/
│   │   ├── test_models.py        # Data model tests
│   │   ├── core/                 # Core module tests
│   │   ├── integrations/         # Integration tests
│   │   └── analysis/             # Analysis tests
│   └── api/                      # API endpoint tests
└── README.md                     # This file
```

## Test Categories

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **API Tests**: Test HTTP endpoints using FastAPI TestClient

### Test features
- Unit tests for models, schemas, and core logic
- Integration tests for API endpoints
- Mocked external services (Trello, Confluence, OpenAI)
- Temporary test databases and directories
- Fixtures for common test data

## Coverage Reports

After running tests, coverage reports are generated in:
- **HTML Report**: `htmlcov/index.html` (open in browser)
- **Terminal Report**: Shown in test output
- **XML Report**: `coverage.xml` (for CI/CD)

## Notes

- Tests use temporary directories and databases to avoid affecting production data
- External services (Trello, Confluence) are mocked to avoid API calls during testing
- Some tests require specific environment setup (see individual test files)

