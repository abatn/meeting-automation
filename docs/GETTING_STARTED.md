# Getting Started — Meeting Automation System

> Abgeleitet aus: ARCHITECTURE.md, ISO27001.md, DATABASE_SCHEMA.md, production/
> Stand: 2026-06-23 | k3s Staging aktiv, 13 Pods, Pipeline 31.7s, Phase 46

## 1. Was ist Meeting Automation?

Multi-Tenant SaaS-Plattform für Meeting-Automatisierung (Tunesien/Maghreb):
- **Recording** via LiveKit WebRTC (Arabisch/Französisch/Englisch)
- **Transcription** via Gladia V2 (Diarization + Speaker-ID)
- **PV-Generierung** via Mistral AI (Strukturierte Sitzungsprotokolle)
- **Action Assignment** via ONNX + Heuristik
- **Multi-Tenancy** mit JWT + client_id Isolation

## 2. Pipeline-Flow (31.7s)

```
Browser → LiveKit Egress → MinIO S3 → Webhook
  → Celery Worker → S3 Download → Gladia (Text+Diarization)
  → Speaker ID (ONNX) → Mistral (PV+Actions) → PostgreSQL
```

| Schritt | Dauer | Service |
|---------|-------|---------|
| S3 Upload/Download | ~2s | Egress → MinIO → Celery |
| Gladia Transcription | ~6s | Gladia V2 API |
| Speaker Identification | ~18s | ONNX Embeddings |
| Mistral PV | ~5s | Mistral AI API |
| DB Persistence | ~1s | PostgreSQL |

## 3. Technologie-Stack

| Komponente | Technologie |
|------------|------------|
| Frontend | React 18, TypeScript, MUI, Redux Toolkit |
| Backend | FastAPI, Python 3.11, SQLAlchemy, Alembic |
| DB | PostgreSQL 15 |
| Cache | Redis 7 |
| Queue | RabbitMQ 3 |
| Storage | MinIO (S3-kompatibel) |
| KI | Gladia V2 (Transcription) + Mistral (PV) |
| Recording | LiveKit (WebRTC) |
| Automation | n8n |
| Doku | OnlyOffice |

## 4. Multi-Tenancy

```
clients (Organisation)
  └── users (Benutzer mit Rollen)
       └── meetings
            ├── recordings → transcriptions
            ├── pvs → pv_sections
            └── actions → assignments
```

**RBAC**: DG (Admin) → Manager → Participant | System Admin | Tech Admin

## 5. ISO 27001 Compliance (6/10 Controls)

| Control | Status |
|---------|--------|
| A.8.24 Secret Management | ✅ K8s Secrets |
| A.8.24 Encryption at Rest | ✅ Fernet AES-128 |
| A.8.26 Tenant Isolation | ✅ client_id Filter |
| A.12.4.1 Audit Logging | ✅ 118+ Logs |
| A.5.17 Auth & RBAC | ✅ JWT + 5 Rollen |
| A.8.20 Network Policies | ✅ 7 Policies deployt |

## 6. Infrastruktur

### Lokal (Docker Compose)
```bash
./setup-system.sh
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# Login: dg@meeting.tn / Password123!
```

### Staging (k3s) — AKTIV
```bash
./setup-kubernetes-staging.sh
# Frontend: http://158.180.18.110:31362 (NodePort)
# Backend: http://158.180.18.110:32222 (NodePort)
# Login: dg@meeting.tn / Password123!
# Pods: 13 Running (backend×2, frontend, celery-worker, celery-beat,
#        postgres, redis, minio, rabbitmq, livekit-server, livekit-egress,
#        onlyoffice, n8n)
```

### Production (k3s)
```bash
./setup-kubernetes.sh
# Docs: docs/production/
```

## 7. Nächste Schritte

### Produktions-Roadmap (5 Sprints)
1. **Storage + HA + Backups** — Longhorn, CloudNativePG, Velero ❌ Offen
2. **Monitoring + HPA** — Prometheus, Grafana, Loki, Auto-Scaling ❌ Offen
3. **GitOps + Environments** — ArgoCD, Kustomize, Namespace-Isolation ❌ Offen
4. **Resource Limits + Probes** — CPU/Memory für alle Workloads ✅ Abgeschlossen (Phase 42-43)
5. **TLS + Registry** — cert-manager, Image-Registry ❌ Offen

### Offen
- HTTPS/TLS implementieren (Sprint 5)
- LiveKit WSS aktivieren (Sprint 5)
- n8n Workflows aktivieren — API Key muss zuerst konfiguriert werden

### Abgeschlossen (Phasen 33-46)
- ✅ k3s Migration (Phase 33)
- ✅ Full Pipeline Test (Phase 34)
- ✅ Hardcoded Werte eliminiert (Phase 37)
- ✅ External Access via NodePort (Phase 39)
- ✅ OnlyOffice NetworkPolicy (Phase 40)
- ✅ LiveKit Egress API Key Fix (Phase 41)
- ✅ Health Probes für 6 Workloads (Phase 42)
- ✅ n8n PostgreSQL Credential Sync (Phase 43)
- ✅ Git Commits (Phase 44)
- ✅ PVC Cleanup (Phase 45)
- ✅ Migration Heads Verifikation (Phase 46)

## 8. Dokumentation

- **Hauptdokument**: `docs/ARCHITECTURE.md`
- **Index**: `docs/DOCUMENTATION_INDEX.md` (113+ Dateien kategorisiert)
- **Produktion**: `docs/production/` (5 Sprints + k3s-Analyse)
- **ISO 27001**: `docs/ISO27001.md`
