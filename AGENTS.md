# AGENTS.md — Meeting Automation

Compact instruction file for future OpenCode sessions. Focus: critical quirks, commands, and constraints that agents would miss.

## Tech Stack
- **Backend**: FastAPI + Python 3.11 + SQLAlchemy async + asyncpg
- **Frontend**: React 18 + TypeScript + Redux Toolkit + Material-UI
- **Database**: PostgreSQL 15 + Redis 7 + Celery (RabbitMQ)
- **Multi-tenant SaaS** with ISO 27001 audit logging

## Critical Quirks

### Async Testing (Non-Obvious)
- Tests use **pytest + pytest-asyncio** 
- **E2E_MODE=true** switches from SQLite to PostgreSQL
- Schema setup: `conftest.py` imports all models, uses `Base.metadata.create_all()` (lines 73-78)
- **NullPool used in tests** (conftest.py:62) — avoids asyncpg enum OID caching issues

### Linting Disabled — DO NOT RE-ENABLE
- **flake8 + mypy disabled in CI** (.github/workflows/backend-ci.yml lines 62-74, commented out)
- 678 issues parked in docs/LINT_ISSUES_2026-04-05.md
- Running locally is fine; CI will not enforce

### Database Driver (Critical)
- Use **asyncpg** driver: `postgresql+asyncpg://...` (not psycopg2)
- No blocking I/O in async functions

### Multi-Tenancy (Non-Negotiable)
- Every DB query MUST filter by `client_id` from JWT token (app/api/deps.py)
- No exceptions — security requirement

### ISO 27001 Compliance
- All data changes must call `audit_service.log_action()`
- No exceptions

## Quick Commands

### Backend
```bash
cd backend

# Tests (SQLite)
pytest tests/ -v

# Tests (PostgreSQL E2E)
E2E_MODE=true pytest tests/e2e/ -v

# Single test
pytest tests/test_meetings.py::test_create_meeting -v

# Dev server
python -m uvicorn app.main:app --reload

# Format
black . && isort .
```

### Frontend
```bash
cd frontend

# Install (npm ci in CI, npm install locally)
npm ci

# Dev server (Vite at localhost:5173)
npm run dev

# Required in CI
npm run lint && npm run type-check && npm run build
```

### Docker
```bash
docker-compose up -d
docker-compose logs -f [service]
docker-compose down -v  # Reset all data
```

## Architecture Notes

- **Authentication**: JWT in httpOnly cookies (X-Client-ID header validation)
- **Entry points**: `backend/app/main.py`, `frontend/src/main.tsx`
- **Redux store**: `frontend/src/store/` (auth, meetings, transcriptions slices)
- **n8n workflows**: `n8n/workflows/*.json` (webhooks at `/webhooks/n8n`)

## Security Compliance
- JWT → httpOnly cookies (prevents XSS token theft)
- X-Client-ID header validated against JWT (multi-tenant defense)
- Logout clears Redux state completely
- Audit logs via `/api/v1/audit/log` endpoint

## Key Files
| File | Purpose |
|------|---------|
| CLAUDE.md | Authoritative patterns and examples |
| backend/conftest.py | E2E_MODE + async test setup |
| backend/app/api/deps.py | client_id extraction |
| frontend/src/services/api.ts | Axios + auth interceptors |
| .env.example | Environment variables |

## Before Making Changes
1. Check CLAUDE.md for domain patterns
2. Verify client_id filtering for any DB query
3. Call audit_service.log_action() for data changes
4. Run: backend → `pytest tests/`, frontend → `npm run lint && type-check`