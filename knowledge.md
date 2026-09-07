# Meeting Automation System - Project Knowledge

## Overview

Multi-tenant SaaS platform for automated meeting management, transcription, PV (Procès-Verbal) generation, and action tracking. Optimized for Tunisia/Maghreb markets with multilingual support (French, Tunisian Arabic, English) and WhatsApp integration.

**ISO 27001 compliant** with full audit trail, RBAC, and encrypted data at rest.

---

## Recent History (August 28 - September 2, 2026)

### Current State
- **Base**: Revert to commit `8f2116ee` (August 5, 2026)
- **Changes since revert**: Sentinel LLM fixes, TIMING logs, CI/CD pipeline fixes

### Timeline of Events

| Date | Event | Impact |
|------|-------|--------|
| **Aug 28** | SIGSEGV crash in Production pipeline | Sentinel LLM crashed with segmentation fault in libggml-cpu.so.0 |
| **Aug 28** | Root cause identified | SoftTimeLimit (540s) killed worker → C++ state corruption → SIGSEGV on retry |
| **Aug 29** | Revert to August 5 state | Removed monitoring, KEDA, Velero, metrics-server (caused CPU issues) |
| **Aug 29** | Port conflict fix | Production YAMLs accidentally applied to staging cluster |
| **Aug 29-30** | CI/CD cleanup | Removed Longhorn references, fixed Velero namespace, explicit file lists |
| **Aug 30** | LiveKit Egress fixes | CPU limits 1→2, room_composite_cpu_cost 1.5→2.0, version pinning v1.9.0 |
| **Aug 30** | Mistral model change | mistral-large → mistral-medium (403 tier_not_allowed error) |
| **Sep 1** | Sentinel ARM64 fix | Disable GGML_NATIVE for QEMU builds |
| **Sep 1** | Rollout timeout increase | 600s → 900s for larger Sentinel-enabled image |
| **Sep 1** | E2E_TEST disabled in staging | Removed E2E_TEST=true from backend container |
| **Sep 2** | TIMING logs restored | get_task_logger restored for visibility |
| **Sep 2** | Production pipeline fix | Race condition, missing ConfigMaps, timeouts resolved |

### Key Fixes Applied

#### 1. SIGSEGV Crash (Aug 28)
- **Problem**: Sentinel LLM (Qwen-1.5B) crashed with segmentation fault
- **Root Cause**: SoftTimeLimit (540s) killed worker → C++ state corruption → SIGSEGV on retry
- **Solution**: Increased task_soft_time_limit to 900s

#### 2. Revert to August 5 (Aug 29)
- **Problem**: Monitoring stack caused 122K Watch-Events, 2% CPU
- **Solution**: Removed Prometheus, Grafana, KEDA, Velero, metrics-server
- **Retained**: Sentinel LLM config, OnlyOffice fixes, LiveKit config, CNPG backups

#### 3. LiveKit Egress (Aug 30)
- **Problem**: WebSocket timeouts, recording failures
- **Solution**: 
  - CPU limits increased (1→2)
  - room_composite_cpu_cost increased (1.5→2.0)
  - Version pinned to v1.9.0 (not :latest)
  - hostNetwork: true for stable connections

#### 4. Sentinel LLM (Sep 1)
- **Problem**: GGML_NATIVE caused build failures on ARM64 QEMU
- **Solution**: Disabled GGML_NATIVE in Dockerfile.sentinel
- **Problem**: Larger image needed more rollout time
- **Solution**: Increased timeout from 600s to 900s

#### 5. TIMING Logs (Sep 2)
- **Problem**: TIMING logs not visible in Celery worker
- **Root Cause**: get_task_logger was replaced with plain logger
- **Solution**: Restored get_task_logger in email_tasks.py, feedback_tasks.py, transcription_tasks.py

#### 6. Production Pipeline (Sep 2)
- **Problem**: Race condition between deploy-production.yml and e2e-tests.yml
- **Solution**: Disabled workflow_run trigger, use manual workflow_dispatch only
- **Problem**: Missing ConfigMaps (backend-config, frontend-nginx, livekit, livekit-egress)
- **Solution**: Added to e2e-tests.yml prod job
- **Problem**: Missing Secrets block
- **Solution**: Added idempotent create-if-not-exists for 8 secrets

### Pipeline Performance (Current)

| Stage | Duration | Status |
|-------|----------|--------|
| S3 Download | ~0.1s | ✅ OK |
| Gladia Transcription | ~6-12s | ✅ OK |
| ONNX Init | ~2-3s | ✅ OK |
| Speaker ID | ~0.7-184s | ⚠️ Variable (depends on segments) |
| Sentinel LLM | ~222-252s | 🔴 Bottleneck (90% of total) |
| Mistral PV | ~4-11s | ✅ OK |
| Persistence | ~0.4-0.6s | ✅ OK |
| **Total** | **~247-460s** | 🔴 Target: ≤90s |

### Known Issues

1. **Sentinel LLM is 90% of pipeline time** - Qwen-1.5B on 1 CPU Core = ~1.2 tok/s
2. **ONNX Thread-Thrashing** - 8 workers on 1 CPU Core = 0.125 cores per worker
3. **Frontend not showing results** - User leaves room before pipeline completes
4. **Production CPU at 70%** - k3s consuming most resources

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript, Material-UI, Redux Toolkit, i18next (RTL support), Vite |
| **Backend** | FastAPI (Python 3.11), SQLAlchemy async, Pydantic, asyncpg |
| **Database** | PostgreSQL 15 (primary), Redis 7 (cache/sessions) |
| **Storage** | MinIO (S3-compatible object storage) |
| **Message Queue** | RabbitMQ 3 + Celery (async tasks) |
| **AI Services** | Gladia V2 (transcription/diarization), Mistral (NLP/PV generation) |
| **Real-time** | LiveKit (recording, egress, WebRTC) |
| **Automation** | n8n (workflow automation, WhatsApp/email integration) |
| **Infrastructure** | Docker Compose (dev), Kubernetes/k3s (prod) |

---

## Project Structure

```
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (auth, meetings, transcriptions, pv, actions, reports, admin, billing)
│   │   ├── core/            # Configuration, database, security (JWT, encryption)
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response validation
│   │   ├── services/        # Business logic (meeting, transcription, PV, action, speaker ID)
│   │   ├── tasks/           # Celery async tasks (email, transcription, data retention)
│   │   ├── middleware/      # ISO 27001 audit logging
│   │   ├── utils/           # PDF export, diarization matching
│   │   └── templates/       # Email templates
│   └── tests/               # Unit and integration tests
├── frontend/                # React application
│   └── src/
│       ├── components/      # Reusable UI components
│       ├── pages/           # Page-level components
│       ├── store/           # Redux slices (auth, meetings, transcriptions)
│       ├── services/        # API client (axios)
│       ├── hooks/           # Custom React hooks
│       └── i18n/            # Internationalization (en, fr-TN, ar-TN)
├── infrastructure/          # Docker/Kubernetes configs
├── n8n/                     # n8n workflow definitions
├── scripts/                 # Utility scripts
└── docs/                    # Architecture and deployment docs
```

---

## Commands

### Backend

```bash
# Install dependencies
cd backend && pip install -r requirements.txt && pip install -r requirements-dev.txt

# Run development server
cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests (SQLite, fast - unit tests only)
cd backend && pytest tests/ -v --cov=app

# Run E2E tests (PostgreSQL + Celery eager mode)
cd backend && E2E_TEST=true pytest tests/e2e/ -v

# Run specific test
cd backend && pytest tests/test_meetings.py::test_create_meeting -v

# Format code (required before commit)
cd backend && black . && isort .

# Type check (optional locally, not enforced in CI)
cd backend && mypy app/

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision -m "description" --autogenerate
```

### Frontend

```bash
# Install dependencies
cd frontend && npm install

# Run development server (Vite at localhost:3000)
cd frontend && npm run dev

# Run lint (required in CI)
cd frontend && npm run lint

# Type check (required in CI)
cd frontend && npm run type-check

# Build for production
cd frontend && npm run build

# Format code
cd frontend && npm run format
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service_name]
# Services: postgres, redis, rabbitmq, minio, backend, frontend, n8n, celery-worker, celery-beat, livekit-server, livekit-egress

# Stop all services
docker-compose down

# Reset all data (clean slate)
docker-compose down -v

# E2E test environment (isolated ports)
docker-compose -f docker-compose.e2e.yml up -d
docker-compose -f docker-compose.e2e.yml down -v
```

---

## Key URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Backend API Docs | http://localhost:8000/api/docs | - |
| Frontend | http://localhost:3000 | - |
| n8n Workflows | http://localhost:5678 | - |
| RabbitMQ | http://localhost:15672 | rabbit_user/rabbit_password |
| MinIO | http://localhost:9001 | minio_user/minio_password |
| PostgreSQL | localhost:5432 | meeting_user/meeting_password |
| Redis | localhost:6379 | redis_password |

---

## Environment Variables

Critical variables (see `.env.example` for full list):

- `DATABASE_URL` - PostgreSQL connection string (use `asyncpg` driver)
- `SECRET_KEY` - JWT secret
- `ENCRYPTION_KEY` - Fernet key for data encryption
- `CELERY_BROKER_URL` - RabbitMQ connection
- `REDIS_URL` - Redis connection
- `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` - LiveKit credentials
- `MISTRAL_API_KEY`, `GLADIA_API_KEY` - AI service keys
- `STRIPE_API_KEY` - Billing integration

---

## Critical Gotchas

### 🔴 E2E_TEST Environment Variable
- **`E2E_TEST=true`** switches from SQLite to PostgreSQL and enables Celery eager mode
- Tests calling `/api/v1/auth/register` (triggers email) **must** use `E2E_TEST=true`
- Without it, `.delay()` tries to connect to RabbitMQ and hangs
- **Common mistake**: Using `E2E_MODE=true` (that's the Python variable name, not the env var)

### 🔴 Multi-Tenancy is Non-Negotiable
- **Every DB query MUST filter by `client_id`** from JWT token
- Use `get_current_client()` from `app/api/deps.py`
- Celery tasks must also receive `client_id` parameter
- **Exception**: Internal endpoints like `/metrics` (Prometheus scraping)

### 🔴 ISO 27001 Compliance
- All data changes must call `audit_service.log_action()`
- No exceptions - this is a security requirement
- AuditMiddleware uses **dedicated AsyncSessionLocal()** session (not request's get_db)

### 🔴 Database Driver
- **Always use asyncpg**: `postgresql+asyncpg://...` (not psycopg2)
- No blocking I/O in async functions
- NullPool prevents enum OID caching issues in tests

### 🔴 Frontend Port
- Vite runs on **port 3000** (not 5173) - configured in `frontend/vite.config.ts`

### 🔴 PV Sections are Encrypted
- Content starts with `gAAAAAB...` (Fernet encryption)
- Don't assume data is missing if you see encrypted strings
- Check `pv_sections` table directly for actual content

### 🔴 Speaker Names
- Always use `profile.resolved_name or profile.name`
- Using just `.name` returns "Speaker 0" instead of real names
- Display Transcript to Mistral: `"Name: ..."` not `"Speaker 0: ..."`

### 🔴 Docker Image Cleanup
- **FORBIDDEN**: `docker system prune`, `docker volume prune`, `docker image prune`
- These delete images k3s containerd depends on → all pods ImagePullBackOff
- Only prune images NOT referenced by any running deployment

### 🔴 LiveKit Pipeline
- **Target**: ≤90s end-to-end (recording → PV saved)
- **Current**: 
  - Complex meetings (multi-speaker): ~3m 10s - 3m 40s
  - 30-second audio: ~2:40 min
- Main bottleneck: Gladia polling (5s intervals → ~110s idle wait)
- Room auto-close: 5min empty timeout — frontend must join room before recording

### 🔴 Confidence NULL vs 0.0
- `None` ≠ `0.0` - NULL means "never measured", 0.0 means "explicitly low"
- Use: `s.mapping_confidence if s.mapping_confidence is not None else 0.5`
- Wrong: `mapping_confidence or 0.0` (treats NULL same as 0.0)

---

## Additional Gotchas (From Recent Incidents)

### 🟡 CI/CD Pipeline Issues
- **deploy-production.yml workflow_run trigger**: Causes race condition with e2e-tests.yml Job 3
- **Solution**: Disable workflow_run, use manual workflow_dispatch only
- **Rollout timeout**: Backend needs 900s (Sentinel image is larger)
- **Missing ConfigMaps**: Always apply backend-config, frontend-nginx, livekit, livekit-egress before deployments

### 🟡 LiveKit Egress Issues
- **WebSocket timeout**: Egress pods need `hostNetwork: true` for stable connections
- **CPU limits**: 
  - **Staging**: CPU 1→2, room_composite_cpu_cost 1.5→2.0 (increased for stability)
  - **Production**: CPU=1, room_composite_cpu_cost=1.5 (not yet updated)
- **Version pinning**: Use `v1.9.0` (not `:latest`) for consistency
- **Image pull**: Use multi-arch images for ARM64/AMD64 clusters

### 🟡 Kubernetes Deployment
- **Secrets**: Must be created before deployment (idempotent create-if-not-exists)
- **ConfigMaps**: Apply before deployments, not after
- **Progress deadline**: Set to 900s for larger images
- **Longhorn CSI**: Don't reference in CI workflows if not installed

### 🟡 Celery/Task Queue
- **TIMING logs**: Use `get_task_logger` (not plain `logger`) for visibility
- **Worker concurrency**: Set `concurrency=CPU*2` for optimal throughput
- **Task acknowledgment**: Use `task_acks_late=True` for reliability

### 🟡 n8n Workflows
- **Activation**: n8n only activates 3/7 workflows on startup
- **Manual activation**: Call `POST /api/v1/workflows/{id}/activate` with `X-N8N-API-KEY`
- **DB changes**: Don't propagate to n8n in-memory state; must DELETE + RE-IMPORT workflow
- **Webhook paths**: Must match between .env and n8n workflow configuration

### 🟡 Audio Processing
- **OGG duration**: `mutagen` not always in prod image → duration = NULL
- **Gladia polling**: Fixed 5s interval → 22 cycles × 5s = 110s idle for 30s audio
- **Pipeline timing varies by audio length**:
  - 30s audio: ~2:40 min total
  - Complex meetings (multi-speaker): ~3m 10s - 3m 40s
- **Solution**: Implement adaptive polling (1s→2s→3s→5s) to reduce idle wait

### 🟡 Security Considerations
- **Cookie path**: Must transform from `/api/` to `/` for browser to send on all requests
- **Secure flag**: Disable for HTTP development (works without HTTPS)
- **python-jose**: Upgrade to 3.4.0 (fixes CVE-2024-33663)

---

## Architecture Highlights

### SaaS Multi-Tenancy Architecture
- **Data Isolation**: Dedicated `clients` table manages organizational units
- **Backend Filtering**: Every API request filtered by `client_id` from JWT
- **RBAC Roles**:
  - **DG (Director General)**: Primary admin for tenant, full visibility
  - **Manager**: Department lead, manages specific users
  - **Participant**: Regular user, own meetings/actions only
  - **System Admin**: Global platform manager (across tenants)
  - **Tech Admin**: Infrastructure monitor (no business data)

### Authentication & RBAC
- JWT in httpOnly cookies (prevents XSS)
- X-Client-ID header validated against JWT (defense-in-depth)
- Session blacklisting in Redis for secure logout
- MFA support via TOTP (pyotp)

### AI Pipeline Flow
```
Meeting Created → LiveKit Room + Egress → MinIO (S3)
  → Celery Worker → Gladia Transcription → Speaker ID
  → Mistral PV Generation → Actions → DB + Audit
```

**Pipeline Performance (Verified 2026-06-23)**:
- Total Pipeline: ~31s (testbibo, staging)
- S3 Upload/Download: ~2s
- Gladia Transcription: 6s (3 utterances, Arabic)
- Speaker Identification: 18s (ONNX embedding + heuristic)
- Mistral PV: 5s (3 sections + action suggestions)
- DB Persistence: 1s

### Celery Configuration
- **Broker**: RabbitMQ (`amqp://rabbit_user:rabbit_password@rabbitmq:5672//`)
- **Backend**: Redis (`redis://redis:6379/2`)
- **Timezone**: Africa/Tunis
- **Beat schedule**: 
  - daily_reminder_task (8:00 AM)
  - cleanup_old_data_task (2:00 AM)
  - check_storage_quotas (every 15 min)
- **Queue isolation**: transcription, email, maintenance
- **Reliability**: task_acks_late=True, worker_prefetch_multiplier=1

### n8n Workflows
- Triggered via webhooks at `/webhooks/n8n`
- **CRITICAL**: Automation API requires `?client_id=...` parameter
- **CRITICAL**: n8n only activates 3/7 workflows on startup; must call `POST /api/v1/workflows/{id}/activate`
- **Key Workflow IDs**:
  - meeting-created: `uB0bPHLt0FNxsaBe`
  - pv-validated: `o9NXKZqiDnksQeO3`
  - transcription-completed: `00tDUsvHjpnWD6oG`
  - daily-reminders: `GpER66AvYwapRNP4`

### Infrastructure
- **Staging (OCI)**: 158.180.18.110 — ARM64 (aarch64)
  - k3s cluster, 4 CPU, 22GB RAM
  - Namespace: `meeting-automation-staging`
  - 14 NetworkPolicies deployed
- **Production (Contabo)**: 169.58.83.32 — AMD64 (x86_64)
  - Namespace: `meeting-automation`
- **Docker images**: Must be multi-arch `linux/amd64,linux/arm64`
- **CRITICAL**: Do NOT assume both servers are the same architecture!

### OnlyOffice Integration
- Document editing + PDF/DOCX conversion
- Real-time collaborative editing via Socket.IO
- Traffic Chain: Browser → nginx-ingress → frontend nginx → onlyoffice

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app initialization, middleware setup |
| `backend/app/core/database.py` | SQLAlchemy engine, session factory |
| `backend/app/core/config.py` | Settings (environment variables) |
| `backend/app/api/deps.py` | Dependency injection (auth, DB, client extraction) |
| `backend/app/tasks/transcription_tasks.py` | Celery pipeline: Gladia → Mistral → PV |
| `backend/app/services/pv_service.py` | Mistral API call (60s timeout, Temperature 0.1) |
| `backend/app/services/assignee_resolver.py` | 6-step assignee resolution |
| `backend/app/services/phonetic_matcher.py` | Double Metaphone for Arabic names |
| `backend/app/middleware/audit_middleware.py` | ISO 27001 audit logging |
| `frontend/src/store/` | Redux slices (auth, meetings, transcriptions) |
| `frontend/src/services/api.ts` | Axios client and API methods |
| `docs/ARCHITECTURE.md` | Detailed system design |
| `docker-compose.yml` | Local development orchestration |

---

## Database Schema Overview

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `clients` | Tenant organizations | id, company_name, subscription_plan, subscription_status |
| `users` | Team members | id, client_id, email, status (ACTIVE/PENDING/DISABLED) |
| `meetings` | Meeting records | id, client_id, title, status, start_time, end_time |
| `recordings` | Audio files | id, meeting_id, file_path, status |
| `transcriptions` | Speech-to-text output | id, meeting_id, full_text, segments (JSONB) |
| `pvs` | Meeting minutes | id, meeting_id, content_html, is_validated |
| `pv_sections` | PV content sections | id, pv_id, title, content, type (summary/decision/action) |
| `actions` | Confirmed action items | id, meeting_id, title, status (PENDING/IN_PROGRESS/COMPLETED/CANCELLED/OVERDUE) |
| `action_suggestions` | AI-suggested tasks | id, meeting_id, title, status (SUGGESTED/ACCEPTED/REJECTED) |
| `audit_logs` | ISO 27001 audit trail | id, client_id, user_id, action, table_name, timestamp |

### RBAC Tables

| Table | Purpose |
|-------|----------|
| `roles` | Role definitions (dg, manager, participant, system_admin, tech_admin) |
| `user_roles` | Many-to-many user-role junction |
| `activation_tokens` | Enterprise onboarding tokens (SHA-256 hashed) |

---

## API Endpoints Overview

### Authentication (`/api/v1/auth`)
- `POST /register` - User registration
- `POST /login` - User login (returns JWT)
- `POST /refresh` - Refresh access token
- `POST /mfa/setup` - MFA setup (returns QR code)
- `POST /mfa/verify` - Verify MFA token

### Meetings (`/api/v1/meetings`)
- `POST /` - Create meeting
- `GET /{meeting_id}` - Get meeting details
- `GET /` - List meetings (with filters)

### LiveKit (`/api/v1/meetings/{meeting_id}/livekit`)
- `POST /token` - Generate LiveKit access token
- `POST /start-recording` - Start Egress recording
- `POST /stop-recording` - Stop recording
- `GET /recording-status` - Get recording status

### AI Insights (`/api/v1/meetings/{meeting_id}/ai-insights`)
- `GET /` - Get transcription, PV, and actions

### Actions (`/api/v1/actions`)
- `POST /` - Create action item
- `PATCH /{action_id}/status` - Update action status
- `GET /` - List actions (with filters)

### Action Suggestions (`/api/v1/actions/suggestions`)
- `GET /{meeting_id}` - Get AI suggestions
- `POST /learn` - Submit accept/reject feedback

### Reports (`/api/v1/reports`)
- `GET /dashboard/{role}` - Role-specific dashboard data
- `GET /export` - Export report (PDF/XLSX)

---

## Cultural Adaptations

### Multilingual Support
- **Arabic (ar-TN)**: Tunisian Arabic with dialectal nuances
- **Arabic (ar-MSA)**: Modern Standard Arabic for formal docs
- **French (fr-TN)**: Tunisian French
- **English (en)**: Standard English

### Code-Switching in Transcription
- Gladia V2 handles Arabic/French/English code-switching natively
- Common in Maghreb region

### Right-to-Left (RTL) Layout
- Dynamic RTL switching via `useRTL.ts` hook
- Material-UI integration for RTL theming
- CSS overrides in `rtl.css`

### Cultural Calendar
- Hijri (Islamic) calendar integration via `useCulturalCalendar.ts`
- Local date formatting (DD/MM/YYYY, HH:mm)

### WhatsApp Integration
- 90% open rate in Tunisia
- Use cases: meeting reminders, action notifications, PV distribution
- Orchestrated via n8n workflows

---

## ISO 27001 Compliance

### Implemented Controls

| Control | Implementation |
|---------|----------------|
| **A.5.17** | JWT auth, RBAC, session blacklisting |
| **A.8.24** | Fernet AES-128 encryption for sensitive data |
| **A.10** | bcrypt password hashing, ENCRYPTION_KEY in K8s Secrets |
| **A.12.4.1** | AuditMiddleware logs all POST/PUT/DELETE |
| **A.5.14** | n8n webhook security (X-Internal-API-Key) |
| **A.8.20** | 14 NetworkPolicies (default-deny + service-specific) |
| **A.8.26** | client_id in all business metrics |
| **A.9** | /metrics internal-only (no Ingress exposure) |

### Security Roadmap
- TLS/HTTPS: cert-manager + Let's Encrypt (Phase 53+55)
- WAF + Rate Limiting: nginx-ingress (Phase 55)
- Vulnerability Scanning: Trivy in CI/CD
- Session Management: Inaktivitäts-Timeout

---

## Testing

### Test Categories

| Category | Files | DB Required | Celery Required | Command |
|----------|-------|-------------|-----------------|----------|
| **Pure Mocks** | `test_action_service.py`, `test_security_migration.py`, `test_fallback_scenarios.py`, `test_diarization_matcher.py`, `test_diarization_service.py` | ❌ SQLite | ❌ No | `pytest <files> -v` |
| **SQLite-safe** | `test_meetings.py`, `test_pv.py`, `test_transcriptions.py`, `test_actions.py`, `test_recordings.py`, `test_reports_api.py`, `test_pdf_export_api.py`, `test_websockets_api.py` | ❌ SQLite | ❌ No | `pytest <files> -v` |
| **Celery-dependent** | `test_audit.py`, `test_auth.py` | ✅ PostgreSQL | ✅ Eager mode | `E2E_TEST=true pytest <files> -v` |
| **Mixed fixtures** | `test_branding.py`, `test_pv_versioning.py`, `test_meeting_planner_extension.py` | ✅ PostgreSQL | ⚠️ If register called | `E2E_TEST=true pytest <files> -v` |

### Test Results (2026-06-04)
| Category | Result |
|----------|--------|
| Unit Tests | 71/71 ✅ (+ 2 xfailed) |
| E2E Smoke Tests | 5/5 ✅ |
| Total Runtime | ~85s |

### E2E Testing Strategy

| Environment | Purpose | Data Isolation | Automated Tests | Trigger |
|-------------|---------|----------------|-----------------|---------|
| **DEV** | Local development | Fresh DB per run | ✅ Full E2E suite | On-demand |
| **STAGING** | Pre-production validation | Dedicated DB | ✅ Full E2E (≥95% pass) | Automatic after main build |
| **PRODUCTION** | Live customer data | Production DB (never reset) | ❌ Smoke tests only | After deployment |

### CI Pipeline
```bash
# Backend (uses PostgreSQL, NOT SQLite)
pytest tests/ --cov=app --cov-report=xml

# Frontend (order matters)
npm run lint
npm run type-check
npm run build
```

### Security Test Coverage
- SQL Injection prevention
- XSS prevention
- IDOR (Insecure Direct Object Reference) protection
- Rate limiting
- Encryption verification
- OWASP Top 10 compliance verified daily

---

## Debugging Guide

### Backend Issues
```bash
# Check backend logs
docker-compose logs -f backend

# Test API endpoint directly
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=dg@meeting.tn&password=Password123!"

# Check database
psql -h localhost -U meeting_user -d meeting_db -c "SELECT * FROM meetings LIMIT 5;"

# Check audit logs (ISO 27001)
psql -h localhost -U meeting_user -d meeting_db -c "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10;"

# Check PV sections (encrypted content)
psql -h localhost -U meeting_user -d meeting_db -c "SELECT id, pv_id, type, LEFT(content, 50) as content_preview FROM pv_sections LIMIT 5;"

# Check speaker profiles
psql -h localhost -U meeting_user -d meeting_db -c "SELECT id, name, resolved_name, sample_count FROM speakers LIMIT 10;"
```

### Frontend Issues
```bash
# Check for type errors
cd frontend && npm run type-check

# Check for lint errors
cd frontend && npm run lint

# Clear node_modules and reinstall
rm -rf node_modules package-lock.json && npm install

# Check Redux state (in browser console)
# window.__REDUX_DEVTOOLS_EXTENSION__ && window.__REDUX_DEVTOOLS_EXTENSION__

# Check API responses (Network tab)
# Look for 401 (auth), 403 (forbidden), 500 (server error)
```

### LiveKit Issues
```bash
# Check LiveKit server
docker logs livekit-server

# Check Egress
docker logs livekit-egress

# Test WebSocket connection
python3 -c "
import asyncio, websockets, ssl
async def test():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    async with websockets.connect('wss://staging.meeting-automation.com/rtc', ssl=ssl_ctx) as ws:
        print('Connected!')
asyncio.run(test())
"

# Check recording status
kubectl get pods -n meeting-automation | grep egress

# Check LiveKit rooms (via API)
curl -X GET http://localhost:7880/rtc -H "Authorization: Bearer <token>"
```

### Celery Issues
```bash
# Check worker logs
docker-compose logs -f celery-worker

# Check task status in Redis
redis-cli GET "celery-task-meta-<task_id>"

# Check RabbitMQ queues
curl -u rabbit_user:rabbit_password http://localhost:15672/api/queues

# Check pending tasks
redis-cli KEYS "celery-task-meta-*" | head -10

# Check failed tasks
redis-cli KEYS "celery-task-meta-*" | xargs -I {} redis-cli GET {} | grep -i error

# Monitor Celery Flower (if running)
# http://localhost:5555
```

### Kubernetes Issues
```bash
# Check pod status
kubectl get pods -n meeting-automation

# Check pod logs
kubectl logs -f deployment/backend -n meeting-automation

# Check events
kubectl get events -n meeting-automation --sort-by='.lastTimestamp'

# Check ConfigMaps
kubectl get configmaps -n meeting-automation

# Check Secrets
kubectl get secrets -n meeting-automation

# Check rollout status
kubectl rollout status deployment/backend -n meeting-automation

# Debug CrashLoopBackOff
kubectl describe pod <pod-name> -n meeting-automation
kubectl logs <pod-name> -n meeting-automation --previous

# Check resource usage
kubectl top pods -n meeting-automation
```

### Database Issues
```bash
# Check connection pool
psql -h localhost -U meeting_user -d meeting_db -c "SELECT count(*) FROM pg_stat_activity WHERE datname='meeting_db';"

# Check for locks
psql -h localhost -U meeting_user -d meeting_db -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Check table sizes
psql -h localhost -U meeting_user -d meeting_db -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Check slow queries
psql -h localhost -U meeting_user -d meeting_db -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

### n8n Issues
```bash
# Check n8n logs
docker-compose logs -f n8n

# List workflows
curl -X GET http://localhost:5678/api/v1/workflows -H "X-N8N-API-KEY: <api-key>"

# Activate workflow
curl -X POST http://localhost:5678/api/v1/workflows/<workflow-id>/activate -H "X-N8N-API-KEY: <api-key>"

# Check webhook status
# Visit http://localhost:5678/workflows to see active webhooks
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| E2E tests hang | Use `E2E_TEST=true` to enable Celery eager mode |
| Missing client_id filter | Use `get_current_client()` from deps.py |
| Skipping audit logs | Call `audit_service.log_action()` after data changes |
| Wrong DB driver | Use `postgresql+asyncpg://` (not psycopg2) |
| Frontend type errors in CI | Run `npm run type-check` before pushing |
| PV shows encrypted data | Content is Fernet encrypted, check `pv_sections` table |
| Tests connect to wrong DB | Check `DATABASE_URL` uses `asyncpg` driver |
| LiveKit WebSocket fails | Ensure `hostNetwork: true` on egress pods |
| Celery tasks hang | Check RabbitMQ connection, use `E2E_TEST=true` for local |
| n8n webhooks 404 | Manually activate workflows via API |
| Rollout timeout | Increase to 900s for larger images |
| Missing ConfigMaps | Apply before deployment, not after |

---

## Quick Reference Card

### 🚀 Common Development Tasks

| Task | Command |
|------|----------|
| Start dev environment | `docker-compose up -d` |
| Stop dev environment | `docker-compose down` |
| Reset all data | `docker-compose down -v` |
| Run backend server | `cd backend && python -m uvicorn app.main:app --reload` |
| Run frontend server | `cd frontend && npm run dev` |
| Run all tests | `cd backend && pytest tests/ -v` |
| Run E2E tests | `cd backend && E2E_TEST=true pytest tests/e2e/ -v` |
| Format code | `cd backend && black . && isort .` |
| Type check frontend | `cd frontend && npm run type-check` |

### 🔍 Quick Debugging

| Issue | Command |
|-------|----------|
| Backend not starting | `docker-compose logs backend` |
| Frontend type errors | `cd frontend && npm run type-check` |
| LiveKit connection failed | `docker logs livekit-server` |
| Celery tasks hanging | `docker-compose logs celery-worker` |
| Database connection issues | `psql -h localhost -U meeting_user -d meeting_db` |
| n8n webhooks 404 | Check workflow activation in n8n UI |

### 📊 Key Metrics to Monitor

| Metric | Location | Threshold |
|--------|----------|-----------|
| Pipeline duration | `docker logs celery-worker | grep TIMING` | ≤90s target |
| Gladia polling time | `gladia_service.py` | 110s idle for 30s audio |
| Celery queue length | RabbitMQ UI | <100 pending tasks |
| Database connections | `pg_stat_activity` | <50 active connections |
| Pod memory usage | `kubectl top pods` | <80% of limits |

### 🔐 Security Checklist

- [ ] Every DB query filters by `client_id`
- [ ] All data changes call `audit_service.log_action()`
- [ ] JWT in httpOnly cookies (not localStorage)
- [ ] X-Client-ID header validated against JWT
- [ ] Sensitive data encrypted at rest (Fernet)
- [ ] No secrets in code (use .env or K8s Secrets)

### 🚨 Emergency Procedures

| Situation | Action |
|-----------|--------|
| Pods CrashLoopBackOff | `kubectl describe pod <pod>` + check logs |
| Database locked | Check `pg_locks` and kill long-running queries |
| Celery worker down | `docker-compose restart celery-worker` |
| LiveKit connection lost | Check `hostNetwork: true` on egress pods |
| n8n workflows inactive | Manually activate via API or UI |

---

## Related Documentation

- `docs/ARCHITECTURE.md` - System design and integration points
- `docs/DATABASE_SCHEMA.md` - Database schema and relationships
- `docs/API.md` - API reference
- `docs/ISO27001.md` - Compliance requirements
- `docs/CULTURAL_ADAPTATIONS.md` - Tunisia/Maghreb market considerations
- `docs/E2E_TESTING_STRATEGY.md` - E2E test approach
- `docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` - Complete LiveKit pipeline
- `docs/PIPELINE_QUICK_WINS.md` - Performance optimization opportunities
- `docs/INTELLIGENT_SPEAKER_ASSIGNMENT.md` - Speaker ID architecture
- `docs/DEPLOYMENT.md` - Deployment guide
- `docs/SIGSEGV_CRASH_ANALYSIS_2026-08-28.md` - SIGSEGV crash root cause
- `docs/REVERT_PLAN_2026-08-29.md` - Revert to August 5 state
- `docs/PORT_CONFLICT_FIX_2026-08-29.md` - Port 7000 conflict fix
- `docs/PIPELINE_STATUS_2026-08-22.md` - Pipeline performance metrics
