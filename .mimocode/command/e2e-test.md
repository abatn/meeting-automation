# Command: E2E Test Runner

Run E2E tests inside Docker with proper isolation and error reporting.

**Description:** Execute E2E tests against the isolated docker-compose.e2e.yml environment. Handles container checks, test selection, and result parsing.

## Usage

```
mimocode run e2e-test [test_filter] [--quick] [--smoke]
```

**Arguments:**
- `test_filter` (optional): Specific test file or pattern (e.g., `test_smoke.py`, `test_pv_generation_flow.py`)
- `--quick`: Run only smoke tests (fastest feedback)
- `--smoke`: Alias for --quick

## Examples

```bash
# Run all E2E tests
mimocode run e2e-test

# Run smoke tests only
mimocode run e2e-test --smoke

# Run specific test file
mimocode run e2e-test test_pv_generation_flow.py

# Run specific test class
mimocode run e2e-test test_phase7_minio_integration.py::TestPhase7MinIOIntegration
```

## Procedure

### Pre-checks
1. Verify E2E docker-compose is running:
   ```bash
   docker-compose -f docker-compose.e2e.yml ps | grep -E "backend|postgres|redis"
   ```
2. If not running, start it:
   ```bash
   docker-compose -f docker-compose.e2e.yml up -d
   sleep 10
   ```

### Test Execution
- **Default (all tests):**
  ```bash
  docker-compose -f docker-compose.e2e.yml exec -T backend \
    pytest tests/e2e/ -v --tb=short 2>&1 | tail -50
  ```

- **Smoke tests:**
  ```bash
  docker-compose -f docker-compose.e2e.yml exec -T backend \
    pytest tests/e2e/test_smoke.py tests/e2e/test_meeting_creation_flow.py tests/e2e/test_assignee_resolver.py tests/e2e/test_intelligent_speaker_assignment.py -v --tb=short 2>&1 | tail -50
  ```

- **Specific file:**
  ```bash
  docker-compose -f docker-compose.e2e.yml exec -T backend \
    pytest tests/e2e/{test_filter} -v --tb=short 2>&1 | tail -50
  ```

### Result Parsing
After test execution, extract summary:
```bash
# Count passed/failed
docker-compose -f docker-compose.e2e.yml exec -T backend \
  pytest tests/e2e/ -v --tb=short 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed" | tail -5
```

### Post-checks
- If failures found, check Celery worker logs:
  ```bash
  docker-compose -f docker-compose.e2e.yml logs celery-worker | tail -30
  ```
- If pipeline issues, check timing:
  ```bash
  docker-compose -f docker-compose.e2e.yml logs celery-worker | grep TIMING
  ```

## Stopping Condition

- All tests pass (349/354 target, ≥95% pass rate)
- OR specific test filter matches and passes
- OR smoke tests pass (quick feedback)

## Notes

- E2E tests use `E2E_TEST=true` environment variable (NOT `E2E_MODE`)
- Tests run against isolated ports: DB 5433, Redis 6380, RabbitMQ 5673, MinIO 9002/9003
- `pytest-rerunfailures` available for flaky tests
- Never use mocks in E2E — all services use real API keys from `.env`
