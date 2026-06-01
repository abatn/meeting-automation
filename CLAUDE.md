# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Meeting Automation** is a multi-tenant SaaS platform for automating meeting management, transcription, PV (Procès-Verbal) generation, and action tracking. Optimized for Tunisia/Maghreb markets with multilingual support (French, Tunisian Arabic, English) and WhatsApp integration.

Key features: ISO 27001 compliance, role-based access control (RBAC), AI-powered transcription and minute generation, action item tracking, and comprehensive audit logging.

## Tech Stack Overview

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript, Material-UI, Redux Toolkit, i18next (RTL) |
| Backend | FastAPI (Python 3.11), SQLAlchemy ORM, Pydantic |
| Database | PostgreSQL 15 (primary), Redis 7 (cache) |
| Storage | MinIO (S3-compatible object storage) |
| Message Queue | RabbitMQ 3 + Celery (async task processing) |
| AI Services | Gladia V2 (transcription/diarization), Mistral (NLP/PV generation) |
| Automation | n8n (workflow automation, WhatsApp/email integration) |
| Containerization | Docker Compose (dev), Kubernetes + Terraform (prod) |

## Project Structure

```
backend/              # FastAPI application
├── app/
│   ├── api/v1/       # REST endpoints (auth, meetings, transcriptions, pv, actions, reports, admin, billing)
│   ├── core/         # Configuration, database, security utilities (JWT, hashing, encryption)
│   ├── models/       # SQLAlchemy ORM models (database schema)
│   ├── schemas/      # Pydantic request/response validation
│   ├── services/     # Business logic (meeting, transcription, PV, action, report, security, diarization)
│   ├── tasks/        # Celery async tasks (email, transcription processing, data retention)
│   ├── middleware/   # ISO 27001 audit logging, request/response tracking
│   ├── utils/        # Helper functions (PDF export, diarization matching)
│   └── templates/    # Email templates
├── tests/            # Unit and integration tests (pytest)
└── pyproject.toml    # Python dependencies and tools config

frontend/            # React application
├── src/
│   ├── components/   # Reusable UI components
│   ├── pages/        # Page-level components
│   ├── store/        # Redux slices and state management
│   ├── services/     # API client (axios) and business logic
│   ├── hooks/        # Custom React hooks
│   ├── i18n/         # Internationalization (Arabic RTL support)
│   └── types/        # TypeScript type definitions
└── package.json      # Node dependencies

infrastructure/      # Docker/Kubernetes configs
data/               # Local development data volumes (PostgreSQL, Redis, MinIO)
n8n/                # n8n workflow definitions (JSON)
scripts/            # Utility scripts (setup, testing, backup)
docs/               # Architecture and deployment documentation
```

## Common Commands

### Backend (Python/FastAPI)

```bash
# Install dependencies (first time)
cd backend && pip install -e .

# Run development server
docker-compose up backend  # Or: cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
cd backend && pytest tests/test_meetings.py -v

# Run single test function
cd backend && pytest tests/test_meetings.py::test_create_meeting -v

# Format code (black, isort)
cd backend && black . && isort .

# Type checking (mypy)
cd backend && mypy app/

# Linting (flake8, similar configuration in pyproject.toml)
cd backend && flake8 app/

# Database migrations (Alembic)
cd backend && alembic upgrade head  # Apply pending migrations
cd backend && alembic downgrade -1   # Revert last migration
cd backend && alembic revision -m "description" --autogenerate  # Generate new migration

# Check API documentation
# After running backend: http://localhost:8000/api/docs (Swagger UI)
```

### Frontend (React/TypeScript)

```bash
# Install dependencies
cd frontend && npm install

# Run development server
cd frontend && npm run dev  # http://localhost:5173

# Run tests
cd frontend && npm test

# Build for production
cd frontend && npm run build

# Lint code
cd frontend && npm run lint

# Format code
cd frontend && npm run format

# Type checking
cd frontend && npm run type-check
```

### Docker Compose (All Services)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service_name]
# Services: postgres, redis, rabbitmq, minio, backend, frontend, n8n, celery

# Stop all services
docker-compose down

# Reset all data (clean slate)
docker-compose down -v

# Rebuild a specific service
docker-compose up --build [service_name]
```

### Celery Task Queue

```bash
# Start Celery worker (for async tasks)
cd backend && celery -A app.tasks worker --loglevel=info

# Check task status in Redis
cd backend && python -c "from app.core.config import settings; import redis; r = redis.from_url(settings.REDIS_URL); print(r.keys('*'))"
```

## Architecture Highlights

### Authentication & Multi-Tenancy
- **JWT-based auth** with refresh tokens. Every API request is validated by `client_id` in the JWT.
- **RBAC roles**: DG (admin), Manager (department lead), Participant (user), System Admin (platform), Tech Admin (infra).
- **Multi-tenancy**: All core entities linked via `client_id`; backend strictly filters queries by tenant.

### AI & ML Feedback Loop
- **Transcription**: Gladia V2 handles French/Arabic/English code-switching and speaker diarization.
- **PV Generation**: Mistral generates structured meeting minutes; users accept/reject suggestions.
- **Action Suggestions**: Separate from confirmed actions; stored in `action_suggestions` table to build a human-in-the-loop dataset for future model fine-tuning.

### Async Task Processing
- **Celery + RabbitMQ** for background jobs: email notifications, transcription processing, data retention cleanup.
- **Task Scheduling**: Celery Beat for periodic tasks (daily reminders, MRR recalculation).
- **Status Tracking**: Redis stores task state; webhooks notify the frontend of completion.

### n8n Workflows
- Triggered by webhook calls from the backend (`POST /webhooks/n8n`).
- Examples: `meeting-created`, `audio-uploaded`, `pv-validated`, `daily-reminders`, `user-invited`.
- Integrates with external APIs: WhatsApp Business, SendGrid, Stripe.

### Database Schema
- **Clients**: Tenant organizations; root of data isolation.
- **Users**: Team members with roles; linked to clients.
- **Meetings**: Core entity; records participants, duration, status, and client.
- **Recordings**: Audio files (stored in MinIO); linked to meetings.
- **Transcriptions**: Speech-to-text output with speaker/diarization; produced by Gladia.
- **PVs (Procès-Verbal)**: Generated meeting minutes; versioned with accept/reject history.
- **Actions**: Confirmed action items assigned to participants.
- **ActionSuggestions**: ML-proposed actions; separate to avoid polluting official record.
- **Audit Log**: ISO 27001 compliance; tracks all data changes and user actions.

### Security & Compliance
- **ISO 27001 Audit Logging**: Every request/response logged with user, client, resource, and action.
- **Password Security**: Hashed with bcrypt; PENDING users have temporary tokens.
- **Data Encryption**: Sensitive fields encrypted at rest.
- **CORS & CSRF**: Properly configured; JWT tokens in Authorization headers.

## Development Workflow

### Before Making Changes
- **Read CLAUDE.md in the docs/ folder** for domain-specific guidance (cultural adaptations, Islamic calendar, Arabic RTL considerations).
- **Check docs/ARCHITECTURE.md** for system boundaries and integration points.
- **Ask clarifying questions** if requirements are unclear (target: 95% confidence before coding).

### Branching & Commits
- Create feature branches from `main`: `git checkout -b fix/issue-name` or `feature/new-feature`.
- Commit messages: start with area (e.g., `fix: auth`, `feat: pv-versioning`, `docs: setup guide`).
- Run tests & linting before pushing to ensure CI passes.

### Testing
- **Unit tests**: Test services, models, and utilities in isolation.
- **Integration tests**: Test API endpoints with a real (test) database.
- **E2E tests**: Full workflow tests (meeting creation → transcription → PV generation).
- Test fixture: `backend/tests/conftest.py` provides `db_session`, `client`, `test_user`, `test_meeting`.

### Code Quality
- **Backend**: Black (formatting), isort (imports), mypy (type checking).
- **Frontend**: ESLint (linting), Prettier (formatting), TypeScript strict mode.
- Use `npm run type-check` (frontend) and `mypy app/` (backend) to catch type errors early.

## Important Constraints & Decisions

1. **No changes without 95% confidence**: Ask clarifying questions before coding. This is a production system with real users.
2. **Multi-tenancy is non-negotiable**: Every query must be filtered by `client_id`. No exceptions.
3. **ISO 27001 compliance required**: All data changes must be audit-logged. Check `AuditMiddleware` and `audit_service.py`.
4. **AI feedback is human-in-the-loop**: Action suggestions are NOT confirmed actions. Keep them separate to preserve data integrity for future fine-tuning.
5. **RTL & Multilingual support required**: Frontend must handle Arabic RTL layouts (via Stylis RTL plugin). Backend must support Arabic tokenization in NLP.
6. **Error handling for external APIs**: Gladia and Mistral calls can fail or timeout. Always have fallback/retry logic.
7. **Production readiness**: Code must handle graceful degradation, health checks, and monitoring. Check for log levels, exception handling, and idempotency.

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app initialization, lifespan hooks, middleware setup |
| `backend/app/core/database.py` | SQLAlchemy engine, session factory, Base ORM class |
| `backend/app/core/config.py` | Settings (environment variables, defaults) |
| `backend/app/api/deps.py` | Dependency injection (auth, DB session, client extraction) |
| `backend/app/services/security_service.py` | JWT, password hashing, encryption utilities |
| `backend/app/services/diarization_service.py` | Speaker matching logic (ML feedback) |
| `backend/app/tasks/transcription_tasks.py` | Celery tasks for async transcription/PV processing |
| `backend/app/middleware/audit_middleware.py` | ISO 27001 audit logging |
| `frontend/src/store/` | Redux slices (auth, meetings, transcriptions, etc.) |
| `frontend/src/services/api.ts` | Axios client and API methods |
| `docs/ARCHITECTURE.md` | Detailed system design and integration points |
| `docker-compose.yml` | Local development orchestration |

## Common Development Patterns

### Adding a New API Endpoint
1. Create a Pydantic schema in `app/schemas/` for request/response.
2. Create SQLAlchemy model in `app/models/` if needed.
3. Add business logic to `app/services/` (not in the route handler).
4. Define the route in `app/api/v1/[domain].py`.
5. Use dependency injection (`get_current_user`, `get_db`) from `app/api/deps.py`.
6. Always filter by `client_id` from the JWT token.
7. Add audit logging via `audit_service.log_action()`.

### Adding a New Celery Task
1. Define the task in `app/tasks/` with `@celery_app.task` decorator.
2. Handle failures gracefully; log errors and retry on transient failures.
3. Call the task from a route using `task.delay(*args)` or `task.apply_async()`.
4. Store the task ID in Redis or DB for status tracking.
5. Notify the frontend via WebSocket when task completes.

### Frontend State Management (Redux)
1. Create a slice in `src/store/[domain]Slice.ts` with reducers for async thunks.
2. Use `createAsyncThunk` for API calls (auto-handles loading, success, error states).
3. Dispatch thunks from components to update store.
4. Select data with `useSelector()` hooks.
5. Handle error states gracefully; show user-friendly messages.

## Debugging Tips

- **Backend logs**: `docker-compose logs -f backend` or run directly with `--log-level DEBUG`.
- **Database queries**: Enable SQLAlchemy echo: `engine = create_engine(..., echo=True)`.
- **Celery tasks**: Check RabbitMQ management UI: `http://localhost:15672` (guest/guest).
- **Redis cache**: `redis-cli` commands: `KEYS *`, `GET key`, `DEL key`.
- **Frontend API calls**: Check Network tab in browser DevTools; use Redux DevTools for state inspection.
- **n8n workflows**: `http://localhost:5678` - visual debugging and test execution.

## i18n / Internationalisierung (Stand: Mai 2026)

Das Frontend verwendet **react-i18next** mit `useTranslation()` Hook und `t()`-Aufrufen – **durchgängig und korrekt**. Bei Analysen von hartcodierten Strings ist Vorsicht geboten:

### Typische False Positives (keine Änderung nötig)
| Kategorie | Beispiele | Grund |
|-----------|-----------|-------|
| Sprach-Labels | `Français`, `English`, `العربية` | Werden von i18n-Logik gesteuert, keine Übersetzung nötig |
| Produkt-/Techniknamen | `PostgreSQL`, `Redis`, `RabbitMQ`, `n8n`, `Mistral AI`, `Gladia AI`, `Celery`, `Backend`, `Frontend` | Internationale Eigennamen |
| Dateiformate | `PDF`, `Word` | Bereits via `t('pv.format_pdf')` u.ä. |
| Dashboard-Keys | `dashboard.stat_*`, `dashboard.dg_title`, `dashboard.manager_title` | Existieren in Locale-Dateien |
| Audit-Keys | `audit.action.*`, `audit.table.*` | Existieren in Locale-Dateien |
| Allgemeine Keys | `transcription`, `common.language`, `common.language` | Bereits korrekt via `t()` |

### Echte Lücken (wurden gefixt)
- **Dateien ohne `useTranslation`**: `LoginForm.tsx`, `RegisterForm.tsx`, `ActivationPage.tsx`, `AudioRecorder.tsx`, `ClientDetails.tsx` → Import + Hook ergänzt, alle Strings auf `t()` umgestellt
- **Dateien mit lückenhaften `t()`**: `TechnikDashboard.tsx` (35 Fehlstellen), `MeetingRoom.tsx`, `TranscriptionViewer.tsx`, `PVValidator.tsx`, `MeetingPlanner.tsx` → fehlende Strings ergänzt

### Locale-Dateien
- `src/i18n/locales/{en,fr-TN,ar-TN}.json` – alle 3 Sprachen vollständig synchronisiert
- Keys nach Namespaces: `auth.*`, `meetings.*`, `meeting_assistant.*`, `pv.*`, `admin.*`, `clientList.*`, `billing.*`, `common.*`, `team.*`, `actions.*`, `dashboard.*`, `landing.*`, `error.*`, `audit.*`

### Konvention
- `t()` mit Punkt-Notation: `t('auth.login.welcome_back')`
- Variablen: `t('key', { variable })`
- Utility-Files (z.B. `passwordValidation.ts`) können `t()` nicht nutzen → Übersetzung in der rufenden Komponente

## Related Documentation

- **Architecture & Design**: `docs/ARCHITECTURE.md`, `docs/DATABASE_SCHEMA.md`
- **API Reference**: `docs/API.md` (Swagger at `http://localhost:8000/api/docs`)
- **Deployment**: `docs/DEPLOYMENT.md`, `infrastructure/`
- **Compliance**: `docs/ISO27001.md`
- **Cultural Considerations**: `docs/CULTURAL_ADAPTATIONS.md` (Islamic calendar, dialects, etc.)
- **Contributing**: `CONTRIBUTING.md`
