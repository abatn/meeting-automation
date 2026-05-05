# AGENTS.md — Meeting Automation

Compact instruction file for future OpenCode sessions. Focus: critical quirks, async testing setup, and linting parking lot.

## Quick Summary
- **Multi-tenant SaaS**: meeting transcription, PV generation, action tracking
- **Tech**: FastAPI + React + PostgreSQL + Celery (async-first)
- **Async ORM**: SQLAlchemy async + asyncpg driver
- **Key constraint**: Multi-tenancy (client_id filtering) + ISO 27001 audit logging

### 🟢 Security Fixes: All 4 Critical Fixes COMPLETE (May 5, 2026)
- **Fix #1 ✅**: JWT → httpOnly Cookies (prevents XSS token theft)
- **Fix #2 ✅**: X-Client-ID Header Injection (multi-tenant validation)
- **Fix #3 ✅**: Logout Redux State Reset (clears auth state completely)
- **Fix #4 ✅**: Audit-Service Integration (ISO 27001 compliance logging)

See CLAUDE.md for comprehensive guidance (commands, architecture, patterns, code examples).

## Critical Quirks & Constraints

### Async Testing (Non-Obvious!)
- All tests use **pytest + pytest-asyncio** (conftest.py)
- **E2E_MODE env var** switches databases:
  - Unset or false: SQLite (unit/integration tests)
  - true: PostgreSQL (E2E tests)
- **Schema setup**: conftest.py imports all models upfront, uses `Base.metadata.create_all()` (lines 73-78)
- **CI environment**: provides postgres:15 + redis:7 services
- Tests expect `DATABASE_URL` + `REDIS_URL` env vars to be set
- **NullPool used in tests** (conftest.py:62) to avoid asyncpg enum OID caching issues

### Linting Disabled — CRITICAL
- **flake8 + mypy disabled in CI** (.github/workflows/backend-ci.yml lines 62-74, commented out)
- **678 total issues parked** in docs/LINT_ISSUES_2026-04-05.md:
  - 4 critical, 51 high priority, rest medium/low
- **DO NOT re-enable** without addressing all issues (breaking the build)
- Q2 2026 target for systematic fix; currently disabled for fast release
- Running locally for reference is fine; CI will not enforce it

### Database & Driver
- **asyncpg driver required**: `postgresql+asyncpg://...` (not psycopg2)
- asyncpg==0.29.0 in requirements.txt
- No blocking I/O in async functions
- See DATABASE_URL in .env.example

### Multi-Tenancy (Non-Negotiable)
- Every DB query must filter by `client_id` extracted from JWT token (app/api/deps.py)
- No exceptions
- Reference: CLAUDE.md "Authentication & Multi-Tenancy"

### ISO 27001 Compliance
- All data changes must be audit-logged via AuditMiddleware + audit_service.log_action()
- No exceptions
- Reference: CLAUDE.md "Security & Compliance"

## Quick Commands

### Backend (cd backend/)
```bash
# Tests (unit/integration with SQLite)
pytest tests/ -v --cov=app

# Tests (E2E with PostgreSQL)
E2E_MODE=true pytest tests/e2e/ -v

# Format code
black . && isort .

# Type check (informational; not enforced in CI)
mypy app/

# Linting (informational; not enforced in CI)
flake8 app/

# Dev server
python -m uvicorn app.main:app --reload

# Database migrations
alembic upgrade head
```

### Frontend (cd frontend/)
```bash
# Install (use npm ci in CI, npm install locally)
npm ci

# Dev server
npm run dev  # Vite at http://localhost:5173

# Type check (required in CI)
npm run type-check

# Lint (required in CI)
npm run lint

# Build (required in CI)
npm run build
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service]

# Reset all data
docker-compose down -v
```

## Known Issues & Parking Lots
- **Linting**: 678 issues (docs/LINT_ISSUES_2026-04-05.md) — CI disabled until fixed
- **Pre-commit hooks**: Not configured (.pre-commit-config.yaml has TODO placeholder)
- **CONTRIBUTING.md**: Empty placeholder file
- **Backend CI**: Linting steps commented out (backend-ci.yml:62-74)

## Testing Requirements

### Installed Packages
- **Main**: requirements.txt (asyncpg, sqlalchemy, etc.)
- **Dev**: requirements-dev.txt (pytest, pytest-asyncio, pytest-cov, pytest-rerunfailures)

### CI Workflow
- Backend: `pytest tests/ --cov=app --cov-report=xml --cov-report=html`
- Frontend: npm lint, npm type-check, npm build
- Triggered on push/PR to main/develop

## Key Files to Reference
| File | Purpose |
|------|---------|
| CLAUDE.md | Authoritative guidance (commands, patterns, decisions) |
| README.md | High-level project overview |
| docs/ARCHITECTURE.md | System design & integration |
| docs/LINT_ISSUES_2026-04-05.md | Parked linting issues |
| backend/conftest.py | Async test setup + E2E_MODE logic |
| .github/workflows/ | CI pipeline definitions |
| .env.example | Environment variable template |

## Security Fixes Details (May 5, 2026)

### Fix #1: JWT → httpOnly Cookies ✅
- **Frontend**: Updated `frontend/src/services/api.ts`, `auth.ts`, components
- **Backend**: Updated `backend/app/api/v1/auth.py` to set httpOnly cookies
- **Status**: Type-checked ✅, Linted ✅, Built ✅
- **Security**: Prevents XSS token theft, JavaScript cannot access token

### Fix #2: X-Client-ID Header Injection ✅
- **Frontend**: Added request interceptor in `frontend/src/services/api.ts`
- **Backend**: Updated `backend/app/api/deps.py` to validate header against JWT
- **Status**: Multi-tenant validation working, Defense-in-Depth implemented ✅
- **Security**: Backend rejects requests with mismatched client_id (403 Forbidden)

### Fix #3: Logout Redux State Reset ✅
- **Frontend**: Added `logoutThunk` to `frontend/src/store/authSlice.ts`
- **Frontend**: Updated `frontend/src/components/layout/Navbar.tsx` to use thunk
- **Backend**: Verified `/api/v1/auth/logout` endpoint exists and clears cookie
- **Status**: State fully cleared on logout, Protected endpoints blocked ✅
- **Security**: Complete state wipe prevents stale data leakage

### Fix #4: Audit-Service Integration ✅
- **Frontend**: Created `frontend/src/services/auditService.ts` (9 methods)
- **Frontend**: Integrated into `authSlice.ts`, `adminService.ts`, `rooms.ts`, `team.ts`, `meetings.ts`
- **Backend**: Created `/api/v1/audit/log` endpoint in `backend/app/api/v1/audit.py`
- **Status**: E2E tested, audit logs persisted to database ✅
- **Security**: ISO 27001 compliance logging for CREATE, UPDATE, DELETE, LOGIN, LOGOUT

### E2E Test Results
```
✅ Frontend: npm type-check (0 errors), npm lint (0 errors), npm build (success)
✅ Backend: Python syntax valid, import validation passed
✅ Docker: Postgres + Redis up, Database migrations complete
✅ Audit: Endpoint tested, logs persisted to audit_logs table
✅ Login/Logout: Full flow tested, state reset verified
```

## For Agents

Before making changes:
1. Check CLAUDE.md for domain patterns and compliance requirements
2. If adding tests: understand E2E_MODE and conftest.py setup (async-first)
3. If modifying CI: leave linting disabled; document any new checks
4. If querying DB: verify client_id filtering (multi-tenancy non-negotiable)
5. If changing data: ensure audit_service.log_action() is called
6. **NEW**: All 4 security fixes are complete; maintain them in future changes

Ask clarifying questions if requirements are unclear — target 95% confidence before coding.
