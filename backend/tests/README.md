# Mistral Chat Tests Documentation

This directory contains comprehensive tests for the Ollama + Mistral integration in the LexExtract application.

## Test Files Overview

### 1. `test_mistral_chat.py` - Unit Tests for Service Layer
**Purpose:** Test the `query_mistral` function in isolation with mocked HTTP calls.

**Coverage:**
- ✅ Successful API responses
- ✅ Error handling (connection errors, timeouts, HTTP errors)
- ✅ Response parsing and validation
- ✅ Client ID enrichment
- ✅ Edge cases (empty responses, missing keys, etc.)
- ✅ Special characters and unicode handling
- ✅ Long message handling

**Key Features:**
- All HTTP requests are mocked using `unittest.mock.patch`
- Tests various error scenarios without requiring external services
- Validates request parameters and response handling
- Fast execution (< 1 second for all 14 tests)

### 2. `test_chat_endpoint.py` - Integration Tests for API Endpoint
**Purpose:** Test the `/chat` FastAPI endpoint with mocked service calls.

**Coverage:**
- ✅ Successful chat requests
- ✅ Request validation (missing fields, invalid types)
- ✅ Response schema validation
- ✅ Error handling and exception scenarios
- ✅ Edge cases (negative client IDs, large integers, unicode)
- ✅ Content type and JSON handling

**Key Features:**
- Uses FastAPI TestClient for realistic API testing
- Service layer is mocked to isolate endpoint logic
- Tests all validation scenarios
- Validates response structure and status codes
- Fast execution (< 2 seconds for all 19 tests)

### 3. `test_mistral_integration.py` - Integration Tests with Real Service
**Purpose:** Test the full integration with actual Ollama service when available.

**Coverage:**
- ✅ Real API calls to Ollama service
- ✅ Multiple consecutive requests
- ✅ Performance testing
- ✅ Service availability detection
- ✅ Health checks and diagnostics

**Key Features:**
- Automatically skips if Ollama is not available
- Tests actual service responses
- Performance benchmarks
- Service health monitoring
- Slower execution (depends on Ollama response time)

## Running the Tests

### Run All Mistral Tests
```bash
docker-compose exec fastapi pytest tests/test_mistral_chat.py tests/test_chat_endpoint.py -v
```

### Run Individual Test Files
```bash
# Unit tests (fast)
docker-compose exec fastapi pytest tests/test_mistral_chat.py -v

# Endpoint tests (fast)
docker-compose exec fastapi pytest tests/test_chat_endpoint.py -v

# Integration tests (requires Ollama)
docker-compose exec fastapi pytest tests/test_mistral_integration.py -v -s
```

### Run Specific Test Cases
```bash
# Test specific functionality
docker-compose exec fastapi pytest tests/test_mistral_chat.py::TestMistralChat::test_query_mistral_success -v

# Test error handling
docker-compose exec fastapi pytest tests/test_mistral_chat.py -k "error" -v

# Test validation
docker-compose exec fastapi pytest tests/test_chat_endpoint.py -k "invalid" -v
```

## Test Results Summary

### ✅ Current Status (All Passing)
- **Unit Tests**: 14/14 passing
- **Endpoint Tests**: 19/19 passing
- **Integration Tests**: Skip when Ollama unavailable
- **Total Coverage**: 33 core tests passing

### Test Coverage Areas

#### Service Layer (`mistral_chat.py`)
- ✅ API communication
- ✅ Request formatting
- ✅ Response parsing
- ✅ Error handling
- ✅ Client ID enrichment

#### API Endpoint (`/chat`)
- ✅ Request validation
- ✅ Response formatting
- ✅ Error handling
- ✅ Status codes
- ✅ Content negotiation

#### Integration
- ✅ End-to-end workflow
- ✅ Real service interaction
- ✅ Performance metrics
- ✅ Service health checks

## Test Configuration

### Dependencies
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `unittest.mock` - Mocking utilities
- `fastapi.testclient` - API testing
- `requests` - HTTP client testing

### Environment Setup
Tests run inside Docker containers with access to:
- Local Ollama service via `host.docker.internal:11434`
- FastAPI application instance
- Mocked external dependencies

## Debugging Tests

### Common Issues and Solutions

1. **Tests calling real service instead of mocks**
   - Ensure patch decorators target the correct import path
   - Use `app.routers.chat.query_mistral` not `app.services.mistral_chat.query_mistral`

2. **Integration tests skipping**
   - Normal when Ollama is not available
   - Use health check tests to verify service status

3. **Timeout errors**
   - Integration tests may timeout if Ollama is slow
   - Adjust timeout values in service configuration

### Debug Commands
```bash
# Run with verbose output
docker-compose exec fastapi pytest tests/test_mistral_chat.py -v -s

# Run with debug information
docker-compose exec fastapi pytest tests/test_mistral_chat.py -v --tb=long

# Run specific test with print statements
docker-compose exec fastapi pytest tests/test_mistral_integration.py::TestMistralServiceHealth::test_ollama_health_check -v -s
```

## Continuous Integration

### Recommended CI Pipeline
```yaml
# Example GitHub Actions workflow
test_mistral:
  runs-on: ubuntu-latest
  steps:
    - name: Run Unit Tests
      run: docker-compose exec fastapi pytest tests/test_mistral_chat.py -v
    
    - name: Run Endpoint Tests
      run: docker-compose exec fastapi pytest tests/test_chat_endpoint.py -v
    
    - name: Run Integration Tests (Optional)
      run: docker-compose exec fastapi pytest tests/test_mistral_integration.py -v
      continue-on-error: true  # Allow failure if Ollama unavailable
```

## Contributing

When adding new tests:
1. Follow the existing patterns for mocking
2. Add both positive and negative test cases
3. Include edge cases and error scenarios
4. Update this documentation
5. Ensure tests are fast and isolated

## Performance Expectations

- **Unit Tests**: < 1 second total
- **Endpoint Tests**: < 2 seconds total
- **Integration Tests**: 5-30 seconds (depends on Ollama)
- **Full Suite**: < 5 seconds (excluding integration)

## Test Data and Fixtures

Common test data is provided through:
- `sample_chat_requests` fixture
- `mock_ollama_response` fixture
- Helper functions for test data generation

All test data is designed to be:
- Deterministic and reproducible
- Safe for automated testing
- Representative of real-world usage 