# Getting Started — Meeting Automation System

> Abgeleitet aus: ARCHITECTURE.md, ISO27001.md, DATABASE_SCHEMA.md, production/
> Stand: 2026-07-02 | k3s Staging 2-Node Cluster, Phase 122 abgeschlossen, Longhorn 2-Replica, CloudNativePG HA + Velero installiert

## 1. Was ist Meeting Automation?

Multi-Tenant SaaS-Plattform für Meeting-Automatisierung (Tunesien/Maghreb):
- **Recording** via LiveKit WebRTC (Arabisch/Französisch/Englisch)
- **Transcription** via Gladia V2 (Diarization + Speaker-ID)
- **PV-Generierung** via Mistral AI (Strukturierte Sitzungsprotokolle)
- **Action Assignment** via ONNX + Heuristik
- **Multi-Tenancy** mit JWT + client_id Isolation
- **OnlyOffice** für PV-Bearbeitung online (Document Editor)

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

## 3. OnlyOffice PDF Edit Pipeline

```
Frontend (Edit Online) → Backend Config → OnlyOffice Editor (Socket.IO)
  → User bearbeitet → Speichert → Callback
  → Backend: DOCX in S3 + PDF-Konvertierung (0.09s)
  → Download: PDF (2.2s) oder DOCX (sofort)
```

| Schritt | Dauer | Details |
|---------|-------|---------|
| Editor öffnen | ~1s | Config + JWT Token generiert |
| PDF-Konvertierung | 0.09s | OnlyOffice Converter (DOCX→PDF) |
| PDF Download | 2.2s | S3 → Konvertierung → Browser |
| DOCX Download | sofort | S3 → Browser |

## 4. Technologie-Stack

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
| Dokumente | OnlyOffice (PDF/DOCX Edit + Konvertierung) |

## 5. Multi-Tenancy

```
clients (Organisation)
  └── users (Benutzer mit Rollen)
       └── meetings
            ├── recordings → transcriptions
            ├── pvs → pv_sections
            └── actions → assignments
```

**RBAC**: DG (Admin) → Manager → Participant | System Admin | Tech Admin

## 6. ISO 27001 Compliance (6/10 Controls)

| Control | Status |
|---------|--------|
| A.8.24 Secret Management | ✅ K8s Secrets |
| A.8.24 Encryption at Rest | ✅ Fernet AES-128 |
| A.8.26 Tenant Isolation | ✅ client_id Filter |
| A.12.4.1 Audit Logging | ✅ 118+ Logs |
| A.5.17 Auth & RBAC | ✅ JWT + 5 Rollen |
| A.8.20 Network Policies | ✅ 14 Policies deployt |

## 7. Infrastruktur

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
# Frontend: https://staging.meeting-automation.com (nginx-ingress)
# Backend: http://158.180.18.110:32222 (NodePort)
# n8n UI: http://158.180.18.110:31678 (NodePort)
# Login: dg@meeting.tn / Password123!
# Pods: 13 Running (backend×2, frontend, celery-worker, celery-beat,
#        postgres, redis, minio, rabbitmq, livekit-server, livekit-egress,
#        onlyoffice, n8n)
# Memory: 9.7 Gi Limits (5.2 Gi eingespart durch Right-Sizing)
# SMTP: Mailtrap (bulk.smtp.mailtrap.io)
```

### Production (k3s)
```bash
./setup-kubernetes.sh
# Docs: docs/production/
```

## 8. Nächste Schritte

### Produktions-Roadmap (5 Sprints)
1. **Storage + HA + Backups** — Longhorn, CloudNativePG, Velero ❌ Offen
2. **Monitoring + HPA** — Prometheus, Grafana, Loki, Auto-Scaling ❌ Offen
3. **GitOps + Environments** — ArgoCD, Kustomize, Namespace-Isolation ❌ Offen
4. **Resource Limits + Probes** — CPU/Memory für alle Workloads ✅ Abgeschlossen (Phase 42-43)
5. **TLS + Registry** — cert-manager ✅ Abgeschlossen (Phase 53-57), Image-Registry ❌ Offen

### Abgeschlossen (Phasen 33-90)
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
- ✅ n8n NodePort + NetworkPolicy (Phase 47)
- ✅ n8n API Key + 7 Workflows importiert (Phase 48)
- ✅ ISO 27001 Compliance Update (Phase 49-50)
- ✅ k3s Endpoint Fix + cert-manager + nginx-ingress (Phase 53)
- ✅ TLS Certificate (Phase 55-57)
- ✅ LiveKit WebSocket + OnlyOffice Fixes (Phase 56)
- ✅ SSL/TLS vollständig (Phase 57)
- ✅ OnlyOffice PDF Edit Pipeline (Phase 64-73)
- ✅ Celery Worker Memory Fix — Lazy Loading (Phase 77)
- ✅ Tenant Isolation Security Audit (Phase 76)
- ✅ OnlyOffice Download + Callback HMAC Fix (Phase 79)
- ✅ Abo-Minuten + CMS Pricing (Phase 82-83)
- ✅ Contact Funktion — Header + Footer + Auto-Email (Phase 84)
- ✅ Mailtrap SMTP Integration (Phase 85)
- ✅ n8n Workflows dynamisches client_id (Phase 88)
- ✅ Meeting Status Distribution Fix (Phase 88)
- ✅ Resource Right-Sizing — 5.2 Gi eingespart (Phase 89)
- ✅ Celery Worker Memory Decision — 4Gi beibehalten (Phase 90)

## 9. Dokumentation

- **Hauptdokument**: `docs/ARCHITECTURE.md`
- **Index**: `docs/DOCUMENTATION_INDEX.md` (115+ Dateien kategorisiert)
- **Produktion**: `docs/production/` (5 Sprints + k3s-Analyse)
- **ISO 27001**: `docs/ISO27001.md`
- **OnlyOffice Pipeline**: `docs/pipeline-onlyoffice-pdf-edit.md`
