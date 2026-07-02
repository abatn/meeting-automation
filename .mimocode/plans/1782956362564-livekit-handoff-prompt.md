# LiveKit Connection Error — Handoff Prompt for Next Agent

## Current Status (2026-07-02)

### Root Cause IDENTIFIED
**Prometheus Basic Auth is contaminating LiveKit WebSocket traffic.**

nginx `auth_basic` directive for `staging.meeting-automation.com` (from `prometheus-ingress` with `auth-type: basic` annotation) applies to ALL proxied paths on that host, including `/rtc` (LiveKit WebSocket). Browser sends cached `Authorization: Basic xxx` header to LiveKit server, which expects `Authorization: Bearer xxx` (JWT token). LiveKit rejects: "invalid authorization header" → frontend shows "could not establish signal connection: Abort handler called".

### Fix Plan (Phase 122 + 123)

#### Phase 122: IMMEDIATE FIX (5 minutes)
```bash
kubectl delete ingress prometheus-ingress -n monitoring
kubectl delete secret prometheus-htpasswd -n monitoring
```
Verification:
```bash
kubectl exec -n ingress-nginx <pod> -- grep -c "auth_basic" /etc/nginx/nginx.conf
# Expected: 0
```

#### Phase 123: PROPER FIX (separate ticket)
1. DNS A-Record: `monitoring.meeting-automation.com` → same IP
2. TLS: cert-manager automatic
3. New ingress: `prometheus-ingress` with new host
4. No Basic Auth (internal cluster only)

---

## Full Pipeline Status (from .loop.md)

### Completed Phases (latest first)
- **Phase 121**: CNPG HA Switch — Backend DATABASE_URL migrated from standalone PostgreSQL to CNPG (2-replica HA). Data migrated (49 meetings, 44 recordings, 5142 audit logs). Login verified.
- **Phase 120**: ArgoCD 100% functional — StatefulSet/PVC fix, image tags pinned, NPs corrected, Git YAMLs aligned with cluster state.
- **Phase 119**: Pipeline 100% — Phase 113 fixes restored. Egress WS_URL → DNS name, DNS egress rule, redis ingress for egress+server.
- **Phase 118**: ArgoCD SOPS Integration — sops 3.9.4 binary, age-key secret, configManagementPlugins.
- **Phase 117**: Monitoring Intelligence — 3 Custom Grafana Dashboards, 16 Recording Rules, 16 Alerts, 5 SLOs, HTTP Request Metrics.
- **Phase 116**: TechnikDashboard Features — Pod Manager, Redis Manager, Storage Manager.
- **Phase 115**: TechnikDashboard OpenHive cleanup.
- **Phase 114**: OpenHive + Supabase removed from deployment.
- **Phase 113**: Image Repair + Egress NetworkPolicy Fix — All 17 pods running.
- **Phase 112**: Backend Repair — CNPG connection + data migration. cnpg-policy NetworkPolicy was blocking TCP.
- **Phase 106**: LiveKit Egress + Pipeline Fix — CPU limit, API secret, bucket fallback, frontend state machine.
- **Phase 105**: Meeting Recording Start/Stop Bug Fix — isStarting guard, pollAIInsights fix.
- **Phase 104**: ArgoCD + OpenHive Vollintegration.
- **Phase 99**: GitOps + Secrets — ArgoCD v2.11, SOPS.
- **Phase 98**: TechnikDashboard Monitoring Redesign.
- **Phase 96**: Login-Fix + Egress-Fix + NP Hardening.
- **Phase 95**: LiveKit Egress Fix + NP.
- **Phase 94**: ISO 27001 Compliance + Multi-Tenant Monitoring.
- **Phase 93**: Test Suite Fix — 366 passed, 0 failed.

### Pending Work
- **Phase 107**: Gladia Diarization — Speaker Separation (max_speakers parameter missing)
- Standalone PostgreSQL removal (redundant after CNPG)
- Meeting "test STARTAI A" recording pipeline test (blocked by LiveKit bug)

### Architecture
- **2 nodes** (k3s ARM64): Node 1 = app workloads, Node 2 = data infra + monitoring
- **Backend**: FastAPI + SQLAlchemy async + asyncpg, PostgreSQL (CNPG 2 replicas), Redis, RabbitMQ, Celery
- **Frontend**: React 18 + TypeScript + Redux Toolkit + Material-UI + Vite
- **LiveKit**: Server v1.13.2 (hostNetwork=true, Node 2), Egress (hostNetwork removed)
- **Monitoring**: Prometheus, Grafana, AlertManager, Loki, Promtail, 14 NetworkPolicies
- **GitOps**: ArgoCD v2.11.3 (selfHeal=false, prune=false), SOPS age-key
- **Domain**: staging.meeting-automation.com (Cloudflare)

### Key Files
- `.loop.md` — Main project log (834+ lines, Phases 91-121)
- `AGENTS.md` — Agent instructions, critical quirks, quick commands
- `docs/LIVEKIT_PRODUCTION_ARCHITECTURE.md` — LiveKit connection flow
- `docs/PIPELINE_QUICK_WINS.md` — Performance optimization
- `backend/app/api/v1/livekit.py` — LiveKit token endpoint
- `frontend/src/components/meetings/MeetingRoom.tsx` — Browser → LiveKit connection

### Test Users
- `tech@meeting.tn` / `Password123!` (client_id: `e052b451-0cc3-4932-9c68-7c46240b1936`)
- `batniniabdelkader@yahoo.com` (client_id: `871a3be3-6332-4c10-aeb7-04695a598e88`)

### Access
- Backend: `https://staging.meeting-automation.com/api/v1/auth/login`
- Grafana: `https://staging.meeting-automation.com/grafana` (admin/admin123)
- Prometheus: `https://staging.meeting-automation.com/prometheus` (admin:Admin@123!) — **WILL BREAK after Phase 122**
- ArgoCD: admin / `sHy9ErW4UjfQHkMs`
- Kubeconfig: `~/.kube/config-staging`

---

## Next Steps for Continuing Agent
1. Execute Phase 122: Delete `prometheus-ingress` + `prometheus-htpasswd`
2. Verify: `grep -c "auth_basic" /etc/nginx/nginx.conf` → 0
3. Test: User joins LiveKit room → no "Abort handler called" error
4. Plan Phase 123: monitoring.meeting-automation.com domain
5. Update `.loop.md` with Phase 122 completion
