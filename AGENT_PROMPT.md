# Agent Prompt — Meeting Automation Continued Work

You are continuing work on the **meeting-automation** project — a multi-tenant SaaS for AI-powered meeting management (transcription, PV generation, action items) with k3s infrastructure.

## Critical Context (Read These First)

1. **AGENTS.md** — Tech stack, quick commands, critical quirks, all conventions
2. **.loop.md** — Phase tracking, harte lessons, user decisions (authoritative)
3. **CLAUDE.md** — If exists, comprehensive project patterns

## Current State (as of 2026-07-28)

### Infrastructure
- **Production (Contabo)**: `169.58.83.32` — k3s v1.36.2+k3s1, namespace `meeting-automation`, domain `meeting-automation.com`
- **Staging (OCI)**: `158.180.18.110` — k3s v1.35.5+k3s1, namespace `meeting-automation-staging`, domain `staging.meeting-automation.com`
- **GitHub Repo**: `abatn/meeting-automation` (public)
- **Docker Hub**: `batnini/meeting-automation-backend:latest`, `batnini/meeting-automation-frontend:latest`

### CI/CD Pipeline (ALL GREEN)
- `backend-ci.yml` → Tests ✅ (4m46s)
- `docker-build.yml` → Build + Push ✅ (8m32s)
- `deploy-production.yml` → Deploy to Contabo ✅ (9m50s)
- **Trigger**: Push to `main` → `docker-build.yml` → `deploy-production.yml` (workflow_run)
- **Deploy key**: `~/.ssh/deploy-contabo` (ed25519), GitHub secret `CONTABO_SSH_KEY`
- **Kubeconfig prod**: `~/.kube/config-prod` (server: `https://169.58.83.32:6443`)

### Production Secrets
- Secrets are **NOT in git** (removed 2026-07-28). See `infrastructure/kubernetes/production/secrets-template.yaml` for structure.
- `deploy-production.yml` only applies secrets if they don't exist (won't overwrite manual changes)
- To update secrets: SSH to Contabo, `kubectl edit secret <name> -n meeting-automation`

### Key Findings This Session
1. **GitHub Billing Block**: Was blocking CI. Fixed by making repo public.
2. **Backend CI**: All tests pass (291+ passed, the old "9 failures" from `.loop.md` were already fixed)
3. **OnlyOffice Production**: ConfigMap `onlyoffice-custom-config` + emptyDir + CoreDNS NodeHosts patch applied and verified working
4. **Secrets Security**: 7 production secret YAML files removed from git tracking
5. **Deploy workflow**: Now only applies secrets if they don't exist (prevents overwriting)

## What's Still Open

### High Priority
| # | Task | Details |
|---|------|---------|
| 1 | **Commit uncommitted changes** | Secrets removal, OnlyOffice fix, deploy workflow update — all on disk but NOT committed |
| 2 | **Phase 185: Consent Gate Softening** | 3 code fixes in `recording_service.py` and `livekit.py` — change 403 blocks to warning logs (see `.loop.md` Phase 185) |
| 3 | **Backend CI linting** | Disabled in CI (678 issues in `docs/LINT_ISSUES_2026-04-05.md`) — fix when ready |
| 4 | **OnlyOffice Ingress Route** | Production ingress (`ingress-prod.yaml`) may need `/doc/` route for OnlyOffice (check if editor works end-to-end) |

### Medium Priority
| # | Task | Details |
|---|------|---------|
| 5 | **Staging cleanup** | 854 evicted pods — run `kubectl delete pods --all-namespaces --field-selector=status.phase=Failed --grace-period=0 --force` via `~/.kube/config-staging` |
| 6 | **Smoke-Test in CI** | Add health check + login test to `deploy-production.yml` after rollout |
| 7 | **Prometheus/Grafana on production** | YAMLs exist in `infrastructure/kubernetes/production/monitoring/` but not verified |
| 8 | **OnlyOffice end-to-end test** | Verify editor actually loads a PV document (not just healthcheck) |

### Low Priority
| # | Task | Details |
|---|------|---------|
| 9 | **Pipeline performance** | Target ≤90s, currently ~3m10s. See `docs/PIPELINE_QUICK_WINS.md` |
| 10 | **Staging CI/CD** | No `deploy-staging.yml` workflow yet |
| 11 | **CNPG cluster upgrade** | Production has 3 instances, check if all healthy |
| 12 | **n8n workflow activation** | Only 3/7 auto-activate, rest need manual activation |

## Architecture Quick Reference

### LiveKit Pipeline (Core Feature)
```
Browser → Create Room → Start Recording → LiveKit Egress → MinIO (S3)
  → Webhook → Celery Worker → Gladia (transcription)
  → Speaker ID (ONNX embeddings + Double Metaphone)
  → Mistral (PV generation, Temperature 0.1)
  → Save to DB + Audit Log
```
- **Key files**: `backend/app/tasks/transcription_tasks.py`, `backend/app/services/pv_service.py`
- **Webhook**: `/livekit/webhooks` (dedup via Redis SETNX)
- **Timing**: Add `TIMING:` logs for optimization

### Multi-Tenancy (Non-Negotiable)
- Every DB query MUST filter by `client_id` from JWT token
- X-Client-ID header validated against JWT
- Celery tasks must receive `client_id` parameter

### Consent System (Phase 185 in progress)
- C1 (AUDIO), C2 (VOICE), C3 (SHARING), C4 (STORAGE)
- **User decision**: SOFT gate (warning, not block). DG consent = company-wide consent.
- Fixes needed in `recording_service.py` and `livekit.py`

## SSH Access

| Host | User | Auth | Kubeconfig |
|------|------|------|-----------|
| `169.58.83.32` (Production) | `root` or `meeting` | SSH key `~/.ssh/meeting` | `~/.kube/config-prod` |
| `158.180.18.110` (Staging) | `meeting` | SSH key (not configured from this machine) | `~/.kube/config-staging` |

## Deploy Commands

```bash
# Production (Contabo)
export KUBECONFIG=~/.kube/config-prod
kubectl get pods -n meeting-automation

# Staging (OCI)
export KUBECONFIG=~/.kube/config-staging
kubectl get pods -n meeting-automation-staging

# Push deploy (triggers CI/CD automatically)
cd /home/opc/meeting-automation
git add -A && git commit -m "feat: description" && git push origin main
```

## Common Pitfalls (from AGENTS.md)

1. **E2E_TEST=true** is the env var (not E2E_MODE)
2. **asyncpg** driver (not psycopg2)
3. **client_id filtering** on every DB query
4. **audit_service.log_action()** on every data change
5. **Temperature 0.1** for Mistral (not 0.7)
6. **resolved_name** for speakers (not .name)
7. **Confidence NULL ≠ 0.0** — NULL = never measured, 0.0 = explicitly low
8. **Never `docker system prune`** on k3s nodes
9. **OnlyOffice**: `storage.externalHost` must match domain, `secure_link_secret` must match `SECURE_LINK_SECRET` env var
10. **Secrets NOT in git** — use `secrets-template.yaml` for structure

## What NOT to Do

- Don't re-enable flake8/mypy in CI until the 678 issues are fixed
- Don't delete error monitoring (Löschen ist verboten)
- Don't use `docker system prune` or `k3s ctr images prune --all`
- Don't commit secrets to git
- Don't overwrite production secrets via CI/CD deploy
- Don't hardcode `document.url` as public HTTPS in OnlyOffice config (use internal URLs)
