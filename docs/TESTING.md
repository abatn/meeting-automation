# Testing Guide: Meeting Automation System

## Quick Start

### Backend Tests
```bash
cd backend
# Run unit tests
pytest tests/unit
# Run integration tests
pytest tests/integration
# Run security tests
pytest tests/security
```

### Frontend Tests
```bash
cd frontend
# Run component tests
npm test
# Run E2E tests (UI mode)
npm run cypress:open
# Run E2E tests (Headless mode)
npm run cypress:run
```

### Performance Tests
```bash
# Start Locust
locust -f tests/performance/locustfile.py
```

## Test Structure

### 1. Backend
- **Unit Tests (`backend/tests/unit/`)**: Testing models, schemas, and individual service methods.
- **Integration Tests (`backend/tests/integration/`)**: End-to-end meeting lifecycle (Create -> Upload -> Transcribe -> PV -> Action).
- **Security Tests (`backend/tests/security/`)**: SQL Injection, XSS, IDOR, Rate Limiting, and Encryption checks.
- **Audit Tests**: Verifying that all actions are logged and audit logs are immutable.

### 2. Frontend
- **Component Tests (`frontend/src/components/**/*.test.tsx`)**: MUI component rendering, RTL support, and role-based dashboard logic.
- **E2E Tests (`frontend/cypress/e2e/`)**: User journeys for DG, Manager, and Participant roles.
- **I18n Tests**: Language switching and layout mirroring.

### 3. n8n Workflows
- **Workflow Mocks**: Simulating n8n callbacks for transcription and PV generation.
- **Retry Logic**: Testing system behavior when AI services or n8n are unreachable.

## Test Coverage Goals
- **Unit Tests**: > 80% coverage.
- **Critical Paths**: 100% coverage in integration/E2E tests.
- **Security**: OWASP Top 10 compliance verified daily.

## Performance Benchmarks
- **Concurrent Users**: 100 simultaneous dashboard loads.
- **Parallel AI Processing**: 10 concurrent Whisper transcriptions.
- **Memory/CPU**: Tracking usage during heavy load scenarios.

## Continuous Integration
Tests are automatically executed on every Push and Pull Request via GitHub Actions:
- `backend-ci.yml`: Runs pytest suite.
- `frontend-ci.yml`: Runs Jest and Cypress.
- `security-scan.yml`: Performs OWASP ZAP and Trivy scans.