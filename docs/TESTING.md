# Testing Guide: Meeting Automation System

## Quick Start

### Backend Tests

Alle Tests erfordern `E2E_TEST=true` + volle Docker-Infrastruktur.

#### Erforderliche Umgebungsvariablen
```bash
export E2E_TEST=true
export DATABASE_URL="postgresql+asyncpg://meeting_user:meeting_password@localhost:5432/meeting_db"
export REDIS_URL="redis://localhost:6379/0"
export CELERY_BROKER_URL="amqp://rabbit_user:rabbit_password@localhost:5672//"
export SECRET_KEY="dev-secret-key-meeting-automation-2026"
export ENCRYPTION_KEY="6AfRJonLMRY0ZXZ7W6rmFISWHurdK_AfQ1vjK2WZ3t4="
export TOTP_ENCRYPTION_KEY="MWF5UYgUBBiaPQB-tRw5hoCA_CGsQxDUnYVYFtiMsK4="
```

#### Alle Tests ausführen
```bash
cd backend
python -m pytest tests/ -v
```

#### Nur E2E Smoke Tests
```bash
cd backend
python -m pytest tests/e2e/test_smoke.py -v
```

#### Ergebnis (Stand 2026-06-04)
| Kategorie | Ergebnis |
|-----------|----------|
| Unit Tests | 71/71 ✅ (+ 2 xfailed) |
| E2E Smoke Tests | 5/5 ✅ |

### Frontend Tests
```bash
cd frontend
# Lint + Type Check + Build (required in CI)
npm run lint && npm run type-check && npm run build
```

### Performance Tests
> Performance testing with Locust is planned but not yet implemented.

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
- `ci.yml`: Backend tests (PostgreSQL + E2E_TEST=true) + Frontend (lint+typecheck+build)
- `deploy-staging.yml`: Deploys to staging k3s cluster
- `deploy-production.yml`: Deploys to production k3s cluster (manual trigger)