# AGENTS.MD — Meeting Automation

Compact instruction file for future OpenCode sessions. Focus: critical quirks, commands, and constraints that agents would miss.

## Tech Stack
- **Backend**: FastAPI + Python 3.11 + SQLAlchemy async + asyncpg
- **Frontend**: React 18 + TypeScript + Redux Toolkit + Material-UI + Vite
- **Database**: PostgreSQL 15 + Redis 7 + Celery (RabbitMQ)
- **Real-time**: LiveKit (recording, egress) + MinIO (S3 storage)
- **AI Services**: Gladia V2 (transcription/diarization), Mistral (PV/NLP)
- **Multi-tenant SaaS** with ISO 27001 audit logging

## Critical Quirks

### E2E_TEST Environment Variable (Non-Obvious)
- The env var is **`E2E_TEST=true`** — NOT `E2E_MODE` (that's the Python variable name in conftest.py)
- `E2E_TEST` switches from SQLite to PostgreSQL and enables Celery eager mode (tasks run synchronously)
- **Only `E2E_TEST=true` activates Celery eager mode.** `TEST_USE_PROD_DB=true` and `USE_POSTGRES_FOR_TESTS=true` give PostgreSQL but NOT eager mode.
- Tests calling `/api/v1/auth/register` (which triggers `send_invitation_email.delay()`) **must** use `E2E_TEST=true` — otherwise `.delay()` tries to connect to RabbitMQ and hangs.
- E2E tests use `alembic upgrade head` for schema (not just `Base.metadata.create_all()`)
- E2E tests location: `backend/tests/e2e/` (separate from unit tests)
- E2E docker-compose: `docker-compose.e2e.yml` (isolated DB on port 5433, Redis on 6380, RabbitMQ on 5673, MinIO on 9002/9003)

### Test Categories (Important)
Tests are categorized by external dependency — not all "unit tests" run with SQLite:
- **Pure mocks** (no deps): `test_action_service.py`, `test_security_migration.py`, `test_fallback_scenarios.py`, `test_diarization_matcher.py`, `test_diarization_service.py`
- **SQLite-safe**: `test_meetings.py`, `test_pv.py`, `test_transcriptions.py`, `test_actions.py`, `test_recordings.py`, `test_reports_api.py`, `test_pdf_export_api.py`, `test_websockets_api.py`
- **Celery-dependent** (need `E2E_TEST=true`): `test_audit.py`, `test_auth.py`
- **Mixed fixtures** (need `E2E_TEST=true`): `test_branding.py`, `test_pv_versioning.py`, `test_meeting_planner_extension.py`

### Linting Disabled — DO NOT RE-ENABLE
- **flake8 + mypy disabled in CI** (were in backend-ci.yml, now in ci.yml — never re-enabled)
- 678 issues parked in docs/LINT_ISSUES_2026-04-05.md
- Running locally is fine; CI will not enforce
- Frontend linting is **enabled and required** in CI

### Database Driver (Critical)
- Use **asyncpg** driver: `postgresql+asyncpg://...` (not psycopg2)
- No blocking I/O in async functions
- NullPool prevents enum OID caching issues in tests
- `pool_recycle=1800` prevents stale connections (app/core/database.py)

### Multi-Tenancy (Non-Negotiable)
- Every DB query MUST filter by `client_id` from JWT token (app/api/deps.py)
- No exceptions — security requirement
- X-Client-ID header validated against JWT (defense-in-depth)
- **Celery tasks must also receive `client_id`** — `_process_recording_pipeline` now requires it. API callers pass `client_id` to `process_recording.delay()`.

### ISO 27001 Compliance
- All data changes must call `audit_service.log_action()`
- No exceptions
- Audit logs via `/api/v1/audit/log` endpoint
- **AuditMiddleware uses dedicated `AsyncSessionLocal()` session** — NOT the request's `get_db` session (prevents DB pool exhaustion)
- `db.rollback()` in except-block prevents "Session als FAILED markiert"

### "Löschen ist verboten" Rule (2026-07-01)
- **User**: "wenn wir fehler haben wir behandeln der gründ und beheben es, das löschen die fehlers behandelt nicht die gründe"
- **Translation**: "When we have errors, we treat the cause and fix it. Deleting the error does not treat the cause."
- **Meaning**: Never just delete error reporting (e.g., don't remove a ServiceMonitor that reports a problem — fix the underlying issue so the monitor reports success)
- **Example**: CNPG targets failing → fix CNPG metrics exposure, NOT delete the ServiceMonitor
- **Example**: Duplicate backend targets → fix SM config, NOT delete one SM

### Docker/k3s Image Cleanup — ONLY prune unused (CRITICAL RULE 2026-07-07)
- **FORBIDDEN**: `docker system prune`, `docker volume prune`, `docker image prune`, `k3s ctr images prune --all`
- **Why**: These commands delete images that k3s containerd depends on → all pods ImagePullBackOff → full rebuild required
- **CORRECT**: Only prune images/volumes NOT referenced by any running deployment
- **Safe commands**: `journalctl --vacuum-size=100M`, `sudo find /var/log/pods -name "*.log" -mtime +2 -delete`, `k3s ctr image rm <exact-image>` for specific unused images only
- **Deploy pattern**: build → `k3s ctr image import` → `kubectl set image` → `kubectl rollout restart`. NEVER delete during deploy.

### LiveKit Pipeline (Critical Timing)
- **Recording → PV pipeline**: Target ≤90s end-to-end for Arabic transcriptions
- **Current**: ~14s (testbobo), ~3m 10s (complex meetings)
- **Main bottleneck**: Gladia polling (fixed 5s intervals → ~110s idle wait)
- **PV generation**: Dual-context approach (Sentinel summary + Display Transcript with real names)
- **Temperature 0.1** for deterministic Mistral output (not default 0.7)
- **Timing instrumentation**: Add `TIMING:` logs when optimizing (see transcription_tasks.py pattern)
- **Webhook flow**: LiveKit egress → MinIO upload → Celery async task → Gladia → Mistral → DB
- **Room auto-close**: 5min empty timeout — frontend must join room before recording
- **Webhook dedup**: Redis SETNX (24h TTL, fail-open) prevents duplicate processing
- **Duplicate action prevention**: Guard in `_process_recording_pipeline` (skip if `recording.status == "completed"`) + idempotency check in `_save_pv_and_actions` (skip if action title exists for meeting)
- **Key files**:
  - `backend/app/tasks/transcription_tasks.py` (lines 870-949: PV sections)
  - `backend/app/services/pv_service.py` (Mistral API, 60s timeout, Temperature 0.1)
  - `backend/app/services/assignee_resolver.py` (5-step assignee resolution)
  - `backend/app/services/phonetic_matcher.py` (Double Metaphone for Arabic names)
  - `docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` (complete flow)

### Prometheus Targets (2026-07-01)
- **Backend `/metrics`**: Internal-only (not in Ingress) — no JWT auth needed
- **node-exporter**: hostNetwork pods — use Service ClusterIP relabeling, not node IPs
- **Node 2 firewalld**: Port 9100/tcp must be in trusted zone + source 10.0.0.0/24
- **CNPG**: `enablePodMonitor` deprecated — need PodMonitor resource for port 9187
- **Duplicate SMs**: Keep both but differentiate (e.g., different intervals)

### Speaker Identification (Microsoft Teams Architecture)
- **Always use `resolved_name`** — `match_speaker()` returns `profile.resolved_name or profile.name`
- Using just `.name` returns "Speaker 0" (Gladia label) instead of real names
- **Display Transcript** sent to Mistral: `"Abdelkader Batnini: ..."` not `"Speaker 0: ..."`
- **Assignee Resolution**: 6-step (speaker mappings → participants → phonetic → fuzzy → single speaker → external)
- **Confidence scoring**: 0.30 (external) to 0.95 (exact match)
- **Confidence fallback**: Use 0.5 for NULL (unknown), NOT 0.0. `None` ≠ `0.0`. NULL means "never measured", 0.0 means "explicitly low confidence"
- **Auto-enrollment**: ONNX 192-dim embeddings stored for future matching

## Quick Commands

### Backend
```bash
cd backend

# Tests (SQLite, fast — pure unit tests only)
pytest tests/ -v

# Tests (PostgreSQL + Celery eager — for Celery-dependent tests)
E2E_TEST=true pytest tests/ --ignore=tests/e2e/ --ignore=tests/load/ -v

# Tests (PostgreSQL E2E, slow but real)
E2E_TEST=true pytest tests/e2e/ -v

# Single test
pytest tests/test_meetings.py::test_create_meeting -v

# Dev server
python -m uvicorn app.main:app --reload

# Format (required before commit)
black . && isort .

# Type check (optional locally, not enforced in CI)
mypy app/
```

### Frontend
```bash
cd frontend

# Install (npm ci in CI, npm install locally)
npm ci

# Dev server (Vite at localhost:3001 — temporarily 3001 for staging test, normally 3000)
npm run dev

# REQUIRED in CI (must pass)
npm run lint && npm run type-check && npm run build
```

### Docker
```bash
# Main dev environment
docker-compose up -d
docker-compose logs -f [service]
docker-compose down -v  # Reset all data

# E2E test environment (isolated ports)
docker-compose -f docker-compose.e2e.yml up -d
docker-compose -f docker-compose.e2e.yml logs -f backend
docker-compose -f docker-compose.e2e.yml down -v

# Services: postgres, redis, rabbitmq, minio, onlyoffice, n8n, backend, frontend, celery-worker, celery-beat, livekit-server, livekit-egress
```

### LiveKit E2E Testing
```bash
# Run full pipeline test (recording → transcription → PV)
cd backend
E2E_TEST=true pytest tests/e2e/ -v

# Check LiveKit services
docker ps | grep livekit
docker logs meeting-automation-livekit-server-1
docker logs meeting-automation-livekit-egress-1

# Check Celery worker for pipeline logs
docker logs meeting-automation-celery-worker-1 | grep TIMING
```

## Architecture Notes

### Infrastructure
- **Staging (OCI)**: 158.180.18.110 — ARM64 (aarch64)
- **Production (Contabo)**: 169.58.83.32 — AMD64 (x86_64)
- **Docker images**: Must be multi-arch `linux/amd64,linux/arm64`
- **CRITICAL**: Do NOT assume both servers are the same architecture!

### Authentication
- **JWT** in httpOnly cookies (prevents XSS token theft)
- **X-Client-ID** header validated against JWT (multi-tenant defense)
- Logout clears Redux state completely
- Token blacklist in Redis for secure logout

### Entry Points
- Backend: `backend/app/main.py`
- Frontend: `frontend/src/main.tsx`
- Redux store: `frontend/src/store/` (auth, meetings, transcriptions slices)

### n8n Workflows
- Location: `n8n/workflows/*.json`
- Triggered via webhooks at `/webhooks/n8n`
- Integrations: WhatsApp Business, SendGrid, Stripe
- **Known issue**: n8n webhooks return 404 if workflows not activated (see docs/LIVEKIT_N8N_WORKFLOWS.md)
- **CRITICAL**: Automation API requires `?client_id=e052b451-0cc3-4932-9c68-7c46240b1936` parameter
- **CRITICAL**: n8n only activates 3/7 workflows on startup. Must call `POST /api/v1/workflows/{id}/activate` with `X-N8N-API-KEY` header for others
- **CRITICAL**: DB changes don't propagate to n8n in-memory state. Must DELETE + RE-IMPORT workflow via API
- **Workflow IDs** (runtime, may change on re-import): meeting-created `EbdQNas2d3Q9NzuG`, pv-validated `5_dJFUYSTiynU5Oe0CEBag`, transcription-completed `3`, meeting-status-changed `7`, daily-reminders `4`, user-invited `6`, admin-new-tenant `admin-new-tenant`, audio-uploaded `1`, customer-activated `customer-activated`

### LiveKit Recording Pipeline
```
Meeting Created → LiveKit Room + Egress → MinIO (S3) → Celery Worker
  → Gladia Transcription → Speaker ID → Mistral PV → Actions → DB + Audit
```

**Status tracking**: `recording.status` enum (idle/recording/processing/completed/failed)
**Webhook endpoint**: `/livekit/webhooks` (receives egress_started, egress_ended)
**LiveKit secrets**: Must come from `.env` (LIVEKIT_API_KEY, LIVEKIT_API_SECRET) — no hardcoded values

### Celery Configuration
- **Broker**: RabbitMQ (`amqp://rabbit_user:rabbit_password@rabbitmq:5672//`)
- **Backend**: Redis (`redis://redis:6379/2`)
- **Timezone**: Africa/Tunis
- **Beat schedule**: daily_reminder_task (8:00 AM), cleanup_old_data_task (2:00 AM)
- **Autodiscovered tasks**: email_tasks, transcription_tasks, data_retention, feedback_tasks

## Key Files

| File | Purpose |
|------|---------|
| CLAUDE.md | Authoritative patterns and examples (comprehensive) |
| AGENTS.md | This file — OpenCode agent quick-start |
| backend/tests/conftest.py | E2E_TEST env var + async test setup + NullPool |
| backend/app/api/deps.py | client_id extraction, JWT validation |
| backend/app/tasks/transcription_tasks.py | Celery pipeline: Gladia → Sentinel → Mistral → PV |
| backend/app/services/pv_service.py | Mistral API call (60s timeout), dual-context approach |
| backend/app/services/assignee_resolver.py | 5-step assignee resolution |
| backend/app/services/phonetic_matcher.py | Double Metaphone for Arabic name transliterations |
| backend/app/api/v1/livekit.py | LiveKit token generation, webhook handling |
| backend/app/middleware/audit_middleware.py | ISO 27001 audit logging (dedicated session) |
| frontend/src/services/api.ts | Axios + auth interceptors |
| frontend/src/components/meetings/MeetingRoom.tsx | LiveKit UI, connection state management |
| docker-compose.yml | Main dev environment |
| docker-compose.e2e.yml | E2E test environment (isolated ports) |
| .env.example | Environment variables template |
| docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md | Complete LiveKit pipeline flow |
| docs/PIPELINE_QUICK_WINS.md | Performance optimization opportunities |

## Before Making Changes

1. **Check CLAUDE.md** for domain patterns (comprehensive guide)
2. **Check docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md** for LiveKit pipeline flow
3. **Verify client_id filtering** for any DB query (multi-tenancy requirement)
4. **Call audit_service.log_action()** for data changes (ISO 27001 compliance)
5. **Run tests**:
   - Backend → `pytest tests/` (unit) or `E2E_TEST=true pytest tests/e2e/` (E2E)
   - Frontend → `npm run lint && npm run type-check`
6. **For LiveKit/pipeline changes**: Check docs/PIPELINE_QUICK_WINS.md for known bottlenecks

## CI/CD Pipeline

### GitHub Actions Workflows
- **ci.yml** (single unified pipeline, replaces old backend-ci.yml + frontend-ci.yml + e2e-tests.yml):
  - **Job 1: backend-test** — PostgreSQL 15 + Redis 7 service containers, `E2E_TEST=true`, runs `pytest tests/ --cov=app --cov-report=xml` (ALL tests, not just E2E)
  - **Job 2: frontend-test** — lint → type-check → build
  - **Job 3: build-and-push** — Multi-arch Docker images (amd64+arm64) to Docker Hub (main branch only)
- **deploy-staging.yml** — Deploys to staging k3s cluster (Helm LiveKit, backend, frontend, Celery)
- **deploy-production.yml** — Deploys to production k3s cluster (manual trigger via workflow_dispatch)
- **Disabled** (still exist with .disabled suffix for rollback): backend-ci.yml.disabled, frontend-ci.yml.disabled, e2e-tests.yml.disabled

### Test Command Order in CI
```bash
# Backend (in CI — uses PostgreSQL + E2E_TEST=true, NOT SQLite)
pytest tests/ --cov=app --cov-report=xml

# Frontend (in CI, order matters)
npm run lint
npm run type-check
npm run build
```

## Performance Constraints

### LiveKit Pipeline Target
- **Target**: ≤90s end-to-end (recording start → PV saved)
- **Current**: ~3m 10s - 3m 40s (validated)
- **Main bottleneck**: Gladia polling (fixed 5s intervals → ~110s idle wait)
- **Optimization plan**: See docs/PIPELINE_QUICK_WINS.md
  1. Adaptive Gladia polling (1s→2s→3s→5s) — Est. gain: 60-80s
  2. Early S3 download overlap — Est. gain: 5-10s
  3. Remove artificial delays in speaker batch loop — Est. gain: 5-10s
  4. Celery tuning (prefetch_multiplier=1, task_acks_late=True)

### Timing Instrumentation Pattern
When optimizing pipeline performance, add timing logs:
```python
import time
start = time.time()
# ... operation ...
logger.info(f"TIMING: operation_name_duration={time.time()-start:.2f}s")
```
Extract with: `docker logs celery-worker | grep TIMING`

**Pipeline TIMING Stages** (transcription_tasks.py):
- `s3_download`: Audio download from MinIO
- `onnx_init`: ONNX Runtime initialization
- `gladia_transcription`: Gladia V2 diarization
- `speaker_identification`: Speaker ID (ONNX + heuristic + text)
- `onnx_segment_reassignment`: Per-segment ONNX reassignment
- `sentinel_llm`: Qwen-1.5B summarization (or fallback)
- `mistral_pv`: Mistral PV generation
- `persistence`: DB save (transcription + PV + actions)
- `pipeline_total`: Total pipeline with full breakdown

**Example output:**
```
TIMING: pipeline_total duration=23.45s (s3=0.1s gladia=13.2s speaker=2.1s sentinel=0.0s mistral=8.4s persist=0.3s)
```

## Common Pitfalls

### 1. Wrong Env Var for E2E Tests
- Symptom: E2E tests fall back to SQLite, miss real DB issues
- Fix: Use `E2E_TEST=true` (NOT `E2E_MODE=true` — that's the Python variable, not the env var)

### 2. Missing client_id Filter
- Symptom: Multi-tenant data leakage
- Fix: Use `get_current_client()` from deps.py, filter by `client_id`

### 3. Skipping Audit Logs
- Symptom: ISO 27001 compliance failure
- Fix: Call `audit_service.log_action()` after data changes

### 4. Using psycopg2 Instead of asyncpg
- Symptom: "No async driver" errors
- Fix: Always use `postgresql+asyncpg://` in DATABASE_URL

### 5. Frontend Type Errors Ignored Locally
- Symptom: CI fails on type-check
- Fix: Run `npm run type-check` before pushing

### 6. Assuming PV Sections Are Missing
- Symptom: False alarm "Mistral returns empty data"
- Fix: PV sections are **encrypted** (Fernet). Check `pv_sections` table directly, content starts with `gAAAAAB...`

### 7. Wrong Frontend Dev Port
- Symptom: Can't connect to frontend dev server
- Fix: Vite runs on **port 3001** (temporary override from 3000 for staging test). Config in `frontend/vite.config.ts`

### 8. Forgetting Alembic Migrations in E2E
- Symptom: Schema mismatch in E2E tests
- Fix: E2E docker-compose runs `alembic upgrade head` before tests (not just `Base.metadata.create_all()`)

### 9. Using `.name` Instead of `.resolved_name` for Speakers
- Symptom: PV shows "Speaker 0" instead of real participant names
- Fix: Always use `profile.resolved_name or profile.name` in speaker matching

### 10. test_audit.py or test_auth.py Hangs Without E2E_TEST
- Symptom: Tests hang indefinitely
- Fix: These tests call `/api/v1/auth/register` which triggers `send_invitation_email.delay()`. Without `E2E_TEST=true`, Celery tries to connect to RabbitMQ (unreachable from host). Use `E2E_TEST=true` to enable eager mode.

### 11. Duplicate Actions from Multiple Recording Runs
- Symptom: 3 recording runs create 3x identical actions for the same meeting
- Fix: Guard in `_process_recording_pipeline` (skip if `recording.status == "completed"`) + idempotency check in `_save_pv_and_actions` (skip if action title exists for meeting)

### 12. Confidence NULL vs 0.0 Confusion
- Symptom: `mapping_confidence or 0.0` treats NULL (unknown) same as 0.0 (explicitly low)
- Fix: Use `s.mapping_confidence if s.mapping_confidence is not None else 0.5` — NULL means "never measured", 0.0 means "explicitly rejected"

### 13. Backend /metrics requires JWT auth (blocks Prometheus)
- Symptom: Prometheus backend targets "down" — `{"detail":"Not authenticated"}`
- Fix: Remove `Depends(deps.get_current_user)` from `/metrics` endpoint — it's internal-only (not in Ingress)
- Rule: "Löschen ist verboten — Fehler beheben, nicht löschen"

### 14. hostNetwork pods unreachable from pod network via node IPs
- Symptom: node-exporter targets "down" — `dial tcp 10.0.0.x:9100: connection refused`
- Root Cause: Pod CIDR (10.42.x.x) and node CIDR (10.0.0.x) are different routing domains in k3s
- Fix: Relabel `__address__` to Service ClusterIP in ServiceMonitor

### 15. Node 2 firewalld blocks node-exporter
- Symptom: node-exporter unreachable from Node 1 despite correct NetworkPolicy
- Root Cause: firewalld RUNNING on Node 2 (NOT on Node 1), port 9100 not in trusted zone
- Fix: `firewall-cmd --zone=trusted --add-port=9100/tcp --permanent` + add source `10.0.0.0/24`

### 16. CNPG PostgreSQL has no /metrics on port 5432
- Symptom: CNPG targets "down" — `dial tcp 10.42.5.x:5432: connection refused`
- Root Cause: ServiceMonitor scrapes postgres port (5432), CNPG built-in exporter runs on port 9187
- Fix: Create PodMonitor resource targeting port 9187 (enablePodMonitor deprecated)

### 17. k3s ingress cross-namespace path priority
- Symptom: `/grafana` and `/prometheus` redirect to React frontend `/login`
- Root Cause: Catch-all `/` in staging-ingress wins over specific paths in monitoring-ingress
- Fix: Add explicit path to the catch-all ingress too

### 18. n8n liest Nodes aus workflow_history, NICHT workflow_entity (CRITICAL 2026-08-05)
- Symptom: Credential-ID Update in `workflow_entity` hat keinen Effekt — n8n zeigt weiterhin "Credential does not exist"
- Root Cause: n8n lädt die aktive Workflow-Version aus `workflow_history`, nicht aus `workflow_entity`
- Fix: **BEIDE Tabellen** aktualisieren: `workflow_entity` + `workflow_history`
```sql
UPDATE workflow_entity SET nodes = replace(nodes::text, 'OLD_ID', 'NEW_ID')::jsonb WHERE nodes::text LIKE '%OLD_ID%';
UPDATE workflow_history SET nodes = replace(nodes::text, 'OLD_ID', 'NEW_ID')::jsonb WHERE nodes::text LIKE '%OLD_ID%';
-- Dann: kubectl rollout restart deployment/n8n
```
- CI/CD Auswirkung: Das Deploy-Script muss BEIDE Tabellen in der Credential-ID-Update-Phase ansprechen
- Doku: `docs/N8N_CREDENTIAL_FIX_2026-08-05.md`

## Development Workflow

### Adding a New API Endpoint
1. Create Pydantic schema in `app/schemas/`
2. Create SQLAlchemy model in `app/models/` if needed
3. Add business logic to `app/services/` (not in route handler)
4. Define route in `app/api/v1/[domain].py`
5. Use dependency injection from `app/api/deps.py`
6. **Always filter by client_id** from JWT token
7. Add audit logging via `audit_service.log_action()`

### Adding a Celery Task
1. Define task in `app/tasks/` with `@celery_app.task` decorator
2. **Pass `client_id` parameter** for multi-tenant isolation
3. Handle failures gracefully; retry on transient failures
4. Call task from route using `task.delay(*args, client_id=client_id)`
5. Store task ID for status tracking
6. Notify frontend via WebSocket when complete

### Debugging LiveKit Pipeline
1. Check LiveKit server: `docker logs livekit-server`
2. Check Egress recordings: `docker logs livekit-egress`
3. Check Celery worker pipeline: `docker logs celery-worker | grep "process_recording_pipeline"`
4. Check MinIO storage: `http://localhost:9001` (minio_user/minio_password)
5. Check RabbitMQ: `http://localhost:15672` (rabbit_user/rabbit_password)
6. Extract timing data: `docker logs celery-worker | grep TIMING`

## Related Documentation

- **CLAUDE.md**: Comprehensive project guide (architecture, patterns, conventions)
- **docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md**: Complete LiveKit pipeline flow
- **docs/LIVEKIT_MIGRATION_RECAP_2026-08-06_TO_2026-08-08.md**: LiveKit Helm migration recap (staging + production)
- **docs/LIVEKIT_E2E_VALIDATION_2026-08-09.md**: E2E validation results with log evidence
- **docs/LIVEKIT_INTEGRATION_PLAN.md**: LiveKit integration plan and staging/production comparison
- **docs/PIPELINE_QUICK_WINS.md**: Performance optimization opportunities
- **docs/ARCHITECTURE.md**: System design and integration points
- **docs/DATABASE_SCHEMA.md**: Database schema and relationships
- **docs/API.md**: API reference (also at `http://localhost:8000/api/docs`)
- **docs/ISO27001.md**: Compliance requirements
- **docs/CULTURAL_ADAPTATIONS.md**: Tunisia/Maghreb market considerations
- **docs/E2E_TESTING_STRATEGY.md**: E2E test approach and conventions
- **docs/DUAL_CONTEXT_PV_GENERATION.md**: PV generation with Display Transcript + Temperature 0.1
- **docs/INTELLIGENT_SPEAKER_ASSIGNMENT.md**: AssigneeResolver architecture
- **docs/LIVEKIT_CONNECTION_FIX_2026-06-09.md**: LiveKit connection state fixes
