# Roadmap: Staging vs Production Readiness

> **Aktualisiert**: 2026-06-24 | k3s Migration abgeschlossen, n8n Workflows importiert und aktiv

**Datum:** 2026-04-05  
**Status:** Staging läuft auf k3s, Pipeline funktional ✅, n8n 7 Workflows aktiv ✅  
**Autor:** Claude Code  

---

## 📋 Executive Summary

Das Staging-Cluster läuft auf **k3s v1.35.5+k3s1** auf OCI VM. Die Pipeline (Recording → Transcription → PV) ist funktional und getestet (Phase 33-50). n8n 7 Workflows importiert und aktiv (Phase 48). Nächste Schritte: Production-Readiness (Storage, Monitoring, GitOps, TLS).

**Aktueller Stand:**
1. ✅ k3s Migration abgeschlossen (Phase 33)
2. ✅ Pipeline funktional (Recording → Transcription → PV, ~31s)
3. ✅ Externer Zugriff via Public IP (158.180.18.110)
4. ✅ 13 Pods stabil, alle healthy
5. ✅ Alembic 1 Head, 33 Migrations
6. ✅ n8n 7 Workflows importiert und aktiv (Phase 48)
7. ✅ 13 NetworkPolicies (ISO 27001 A.8.20) aktiv (Phase 47)
8. ❌ HTTP-only (TLS deferred to Sprint 5)

---

## 🎯 Current State Overview

### Staging (k3s)
- ✅ Namespace: `meeting-automation-staging`
- ✅ Alle Infrastruktur-Pods: Running (Postgres, Redis, RabbitMQ, MinIO, n8n, OnlyOffice)
- ✅ Backend: 2/2 Replicas Running, Health Check OK
- ✅ Celery Worker & Beat: 1/1 Running
- ✅ LiveKit + Egress: hostNetwork für UDP/WebRTC
- ✅ Externer Zugriff: NodePort 31362 (Frontend), 32222 (Backend), 31678 (n8n UI)
- ✅ 13 NetworkPolicies (ISO 27001 A.8.20)
- ✅ n8n: 7 Workflows importiert und aktiv (Phase 48), N8N_API_KEY in K8s Secret
- ⚠️ HTTP-only (TLS deferred to Sprint 5)
- ❌ Keine automatisierten Backups
- ❌ Kein Monitoring Stack
- ❌ Secrets nicht SOPS-verschlüsselt (plain YAML)

### Production (Geplant)
- ✅ Namespace: `meeting-automation-prod` (definiert in docs)
- ✅ Network Policies: `default-deny` + allow-regeln (ISO 27001)
- ✅ Resource Limits: Höher (Backend 2Gi RAM, 3 Replicas)
- ⏳ TLS: Let's Encrypt Production Zertifikat (Sprint 5)
- ✅ Monitoring: Custom Dashboard + Prometheus/Grafana geplant
- ✅ Backup: PostgreSQL pg_dump → S3 (täglich 2:00 UTC) + WAL Archiving
- ✅ Secrets: SOPS-verschlüsselt mit age
- ✅ Rate Limiting: 50 req/s (general), 5 req/s (auth)
- ❌ **Infrastruktur nicht provisioniert** (kein Cloud-Cluster)
- ❌ **Production API Keys nicht beschafft**
- ❌ **Terraform Config TODO**
- ❌ **CI/CD Pipeline Job 3 nicht getestet**

---

## 🔍 Detailed Gap Analysis

### 1. External API Credentials

| Service | Staging | Production Required | Status |
|---------|---------|---------------------|--------|
| **Mistral AI** | Test-Key aus `.env` | Production Key (Live) | ❌ Fehlt |
| **Gladia AI** | Test-Key aus `.env` | Production Key (Live) | ❌ Fehlt |
| **SMTP** | SendGrid Sandbox/Local | SendGrid/SES Production | ❌ Fehlt |
| **Stripe** | Test-Mode | Live Mode + Webhooks konfiguriert | ❌ Fehlt |
| **WhatsApp Business** | Test-Token (in `.env`) | Production Token (approved) | ❌ Fehlt |
| **OnlyOffice** | `staging-onlyoffice-secret-jwt-key-2026` | Starkes zufälliges JWT Secret | ⚠️ Schwach |

**Impact:** Production-Deployment ohne echte API-Keys unmöglich. Test-Keys funktionieren nicht im Live-Betrieb.

**Action:** API-Keys bei den jeweiligen Anbietern beantragen/aktivieren und in `backend-secrets.yaml` (SOPS-verschlüsselt) eintragen.

---

### 2. Infrastructure Provisioning

| Komponente | Staging (Lokal) | Staging (Cloud/CI) | Production |
|------------|-----------------|--------------------|------------|
| **Orchestrator** | Kind (Docker) | Kubernetes (Cloud) | Kubernetes (Cloud) |
| **Cluster** | Ein Node (local) | Multi-Node (LoadBalancer) | Multi-Node (HA) |
| **LoadBalancer** | NodePort (nicht host-erreichbar) | ✅ Externe IP + DNS | ✅ Externe IP + DNS |
| **DNS** | Keine | `staging.meeting-automate.tn` | `meeting-automate.tn` |
| **TLS** | HTTP-only | Let's Encrypt Staging optional | Let's Encrypt Production |
| **Terraform** | ❌ Nicht verwendet | ❌ Nicht verwendet (muss geschrieben werden) | ❌ TODO |
| **Backup** | ❌ Keine | ❌ Keine | ✅ Geplant (pg_dump → S3) |
| **Monitoring** | ❌ Kein Prometheus | ❌ Kein Prometheus | ✅ Geplant (Prometheus/Grafana) |

**Impact:** Lokales Staging kann nicht von GitHub Actions Runner erreicht werden (172.18.0.3 ist lokal). CI/CD Job 2 wird fehlschlagen.

**Decision Required:** Cloud Provider wählen (Hetzner, AWS EKS, GKE, Azure AKS, DigitalOcean).

**Action:**
1. Terraform-Config für gewählten Provider schreiben
2. Cloud Cluster provisionieren
3. LoadBalancer External IP erhalten
4. DNS `staging.meeting-automate.tn` auf IP zeigen lassen
5. `kubeconfig` exportieren und in GitHub Secret `KUBE_CONFIG_STAGING` eintragen

---

### 3. Backup & Disaster Recovery

| Backup Typ | Staging | Production Plan |
|------------|---------|-----------------|
| **PostgreSQL Full Dump** | ❌ Nicht implementiert | ✅ Täglich 2:00 UTC (pg_dump gzipped) |
| **WAL Archiving** | ❌ Nein | ✅ Kontinuierlich (Point-in-Time Recovery) |
| **MinIO Versioning** | ❌ Nein | ✅ Aktiviert (Object Versioning) |
| **Offsite Storage** | ❌ Nein | ✅ S3 in anderer Region |
| **Retention Policy** | ❌ Unbegrenzt/Lokal | ✅ 30 Tage für DB-Backups |
| **Restore Testing** | ❌ Nie getestet | ✅ Dokumentiert + getestet |

**Missing Files:**
- `scripts/backup-db.sh` (aktuell TODO/leer)
- `infrastructure/kubernetes/backup-postgres-cronjob.yaml` (nicht vorhanden)

**Impact:** Bei Datenverlust oder DB-Corruption keine Recovery-Möglichkeit in Staging. Production benötigt Backup-Strategie für Compliance (ISO 27001).

**Action:**
1. `scripts/backup-db.sh` implementieren (pg_dump → MinIO/S3)
2. CronJob-Manifest erstellen
3. MinIO Versioning aktivieren
4. Restore-Test durchführen und dokumentieren

---

### 4. Monitoring & Alerting

| Monitoring Komponente | Staging | Production Goal |
|----------------------|---------|-----------------|
| **Custom Dashboard** | ✅ Vorhanden (`/api/v1/admin/metrics`) | ✅ Vorhanden + Historie |
| **Prometheus** | ❌ Nicht installiert | ✅ Geplant |
| **Grafana** | ❌ Nicht installiert | ✅ Geplant |
| **Alertmanager** | ❌ Nicht installiert | ✅ Geplant (Slack/Telegram) |
| **Metrics Historie** | ❌ Nur RAM (keine Retention) | ✅ Zeitreihen-DB (30+ Tage) |
| **Log Aggregation** | ❌ Kein Loki | ✅ Optional (Loki) |

**Current Custom Dashboard:**
- Metriken werden im RAM gehalten → bei Pod-Neustart verloren
- Keine historische Trend-Analyse möglich
- Kein Alerting bei Schwellenwert-Überschreitung

**production Plan** (siehe `PRODUCTION_DEPLOYMENT_PLAN.md` Section 4.2):
1. Backend Metriken im Prometheus Format exportieren (`/metrics` endpoint)
2. Prometheus Stack installieren (Helm: `kube-prometheus-stack`)
3. Grafana Dashboards importieren (Application, DB, AI Services, Infrastructure)
4. Alertmanager Rules definieren (PodDown, HighErrorRate, HighLatency)
5. Alert-Kanäle konfigurieren (Slack/Telegram/Email)

**Impact:** Staging hat kein Monitoring → Probleme nur manuell erkennbar. Production benötigt Proactive Alerting.

**Action:** Nach Staging/Production Deployment Monitoring Stack installieren (Priorität 2).

---

### 5. n8n Workflow Persistence

| Aspekt | Staging | Production Plan |
|--------|---------|-----------------|
| Workflow Storage | ✅ In PostgreSQL (via n8n DB) | ✅ PostgreSQL Persistent |
| PVC für n8n Data | ❌ Nein (ephemeral) | ✅ Geplant (`n8n-pvc.yaml` existiert) |
| Automatischer Import | ✅ API-basiert (Phase 48) | ✅ API-basiert als Fallback |
| Workflow Persistence | ⚠️ Verloren bei Pod-Neustart | ✅ In DB-Backup enthalten |
| N8N_API_KEY | ✅ In K8s Secret `n8n-secrets` | ✅ In K8s Secret |

**Current Issue:** Workflows sind in DB gespeichert (n8n nutzt PostgreSQL), aber bei Pod-Neustart ohne PVC gehen die Workflows verloren → müssen via n8n-API neu importiert werden.

**Production Solution:**
1. `n8n-deployment.yaml` um VolumeMount erweitern (`/home/node/.n8n`)
2. PVC `n8n-pvc` binden (bereits definiert in `n8n-pvc.yaml`)
3. API-Import als Fallback via n8n-API (bereits implementiert in Phase 48)

**Impact:** Workflow-Verlust bei Ausfällen → Automatisierung (Meeting Invites, Transcriptions, Reminders) funktioniert nicht.

**Action:** n8n PVC in Deployment manifesten referenzieren (Priorität 2).

---

### 6. Secrets Management & Security

| Security Aspect | Staging | Production |
|-----------------|---------|------------|
| **Secret Encryption** | ❌ Plain YAML | ✅ SOPS + age verschlüsselt |
| **OnlyOffice JWT Secret** | ⚠️ Schwacher Default (`staging-onlyoffice-secret-jwt-key-2026`) | ✅ Starkes zufälliges Secret |
| **Network Policies** | ⚠️ Teilweise vorhanden | ✅ Vollständig (`default-deny` + Alle Services) |
| **Rate Limiting** | ✅ Traefik Middlewares (50/5) | ✅ Traefik Middlewares (50/5) |
| **JWT Token Expiry** | ✅ 30 Minuten | ✅ 30 Minuten |
| **Audit Logging** | ✅ Implementiert | ✅ Implementiert |
| **Multi-Tenant Isolation** | ✅ Implementiert | ✅ Implementiert |

**Missing in Staging Network Policies:**
- Staging-Verzeichnis `infrastructure/kubernetes/staging/` enthält nur einige Policies
- Production hat vollständige `network-policies.yaml` für alle Services

**Action:**
1. Staging Network Policies vervollständigen (aus Production übernehmen)
2. OnlyOffice Secret in Staging und Production stärker machen (mind. 32 Zeichen zufällig)
3. Backend Secrets in Staging auf SOPS-Verschlüsselung umstellen (optional für Entwicklung)

---

### 7. Resource Scaling

| Service | Staging Replicas | Production Replicas (Plan) |
|---------|------------------|---------------------------|
| **Backend** | 2 | 3 |
| **Frontend** | 2 | 3 |
| **Celery Worker** | 1 | 3 |
| **Celery Beat** | 1 (single) | 1 (mit leader election für HA) |

| Service | Staging RAM Limit | Production RAM Limit |
|---------|-------------------|----------------------|
| **Backend** | 1Gi | 2Gi |
| **Celery Worker** | 512Mi | 2Gi |
| **PostgreSQL** | 512Mi (default) | 4Gi |
| **Redis** | 512Mi | 1Gi |

**Impact:** Production traffic erfordert höhere Ressourcen und Replikate für Hochverfügbarkeit.

**Action:** Resource Limits in Deployment-Manifesten anpassen vor Production-Deploy.

---

### 8. CI/CD Pipeline Integration

**Aktuelle Pipeline** (`.github/workflows/`):
- **Job 1:** Build & DEV E2E ✅ (läuft lokal, 33/33 passed)
- **Job 2:** Deploy zu Staging + Full E2E ❌ **NOCH NICHT GETRIGGERT**
- **Job 3:** Production Deploy + Smoke Tests ⏳ Ausstehend

**Warum Job 2 nicht getriggert:**
1. Lokales Staging (Kind) hat IP `172.18.0.3` → GitHub Actions Runner kann nicht zugreifen
2. Entscheidung: **Kein Cloud-Staging für CI/CD** (vorerst)
3. Fehlende GitHub Secrets? → `KUBE_CONFIG_STAGING` ist gesetzt (aber local Kind)

**Pipeline Requirements für Job 2:**
- ✅ `KUBE_CONFIG_STAGING` Secret (muss auf Cloud-Cluster zeigen)
- ✅ `STAGING_E2E_USER_EMAIL` / `PASSWORD`
- ✅ `MISTRAL_API_KEY_STAGING` / `GLADIA_API_KEY_STAGING`
- ✅ `DOCKERHUB_TOKEN`
- ✅ `staging.meeting-automate.tn` DNS erreichbar

**Alternative:** Job 2 manuell auslassen, direkt zu Production? **Nicht empfohlen** – ohne Staging-E2T keine Validation.

---

## 🚨 Critical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Cloud Staging nicht eingerichtet** | High | Pipeline Job 2 failed → Production ohne E2E-Validierung | Cloud Cluster ASAP einrichten |
| **Production API Keys nicht verfügbar** | High | Production-Deployment unmöglich | Keys vor Go-Live beschaffen |
| **Backup-Strategie fehlt** | Medium | Datenverlust bei DB-Fehler | Backup-CronJob implementieren + testen |
| **Monitoring nicht produktiv** | Medium | Kein Alerting bei Ausfällen | Prometheus/Grafana nach Deploy installieren |
| **n8n Workflows verloren** | Medium | Automatisierung offline | PVC + Import-Skript |
| **Staging Secrets plain YAML** | Low | Secret-Leak bei Commit | SOPS-Verschlüsselung (niedrige Priorität) |

---

## 📊 Priorisierte Action Items

### 🔴 P0 - Muss vor Production erledigt werden

1. **Cloud Kubernetes Cluster bereitstellen** (Staging & Production)
   - Cloud Provider wählen (Hetzner/AWS/GCP/Azure/DigitalOcean)
   - Terraform-Config schreiben (`infrastructure/terraform/`)
   - Cluster provisionieren (mind. 2 Nodes für HA)
   - LoadBalancer + DNS konfigurieren
   
2. **Production API Keys beschaffen**
   - Mistral AI (Production Key)
   - Gladia AI (Production Key)
   - SendGrid/SES (SMTP Production)
   - Stripe (Live Mode + Webhooks)
   - WhatsApp Business API (Production Token)
   
3. **backend-secrets.yaml erweitern**
   - `WHATSAPP_TOKEN` (aktuell nur in prod,但在staging缺失)
   - `ONLYOFFICE_SECRET` (starkes zufälliges Secret)
   - `STRIPE_SECRET_KEY` (falls Stripe aktiv)
   - Werte mit SOPS verschlüsseln

4. **Backup-Strategie implementieren**
   - `scripts/backup-db.sh` schreiben (pg_dump → S3)
   - `infrastructure/kubernetes/backup-postgres-cronjob.yaml` erstellen
   - MinIO Versioning aktivieren
   - Restore-Test durchführen

5. **Terraform Infrastruktur**
   - `infrastructure/terraform/production/main.tf` schreiben
   - Terraform State backend (S3 + DynamoDB Lock) konfigurieren
   - Terraform für Staging-Umgebung schreiben (optional, falls cloud staging)

---

### 🟡 P1 - Innerhalb 1 Woche nach Go-Live

6. **Monitoring Stack deployen**
   - Prometheus (Helm Chart)
   - Grafana (Dashboards importieren)
   - Alertmanager (Slack/Telegram Integration)
   - Custom Metrics in Backend exportieren (`/metrics`)

7. **n8n Workflows persistent machen**
   - `n8n-deployment.yaml` um PVC erweitern
   - Workflows via n8n-API importieren (als Fallback)
   - Backup in DB-Backup integrieren

8. **Staging Network Policies vervollständigen**
   - Alle Network Policies aus Production auf Staging anwenden
   - Testen: Pod-zu-Pod Connectivity einschränken

9. **Pass-Gate stabilisieren** (aktuell bereits 97% ✅)
   - Flaky Tests beheben falls nötig
   - Gate auf 95% halten (nicht niedriger)

---

### 🟢 P2 - Nice-to-have (nach Stabilisierung)

10. **Horizontal Pod Autoscaler (HPA)** für AI-Worker (Gladia/Mistral Proxy)
11. **Log Aggregation** mit Loki (zentrale Logs durchsuchbar)
12. **Canary/Blue-Green Deployments** mit ArgoCD
13. **Auto-Scaling** für Backend und Celery basierend auf CPU/Memory
14. **cert-manager** für automatische TLS-Zertifikate (Staging Let's Encrypt)
15. **Mobile App** (PWA) für Meeting-Aufnahmen
16. **AI Finetuning** (Mistral Prompts für tunesischen Dialekt)

---

## 📅 Recommended Timeline

### Week 1-2: Cloud Infrastructure & API Keys
- [ ] Cloud Provider entscheiden
- [ ] Terraform-Config schreiben und anwenden
- [ ] Kubernetes Cluster provisionieren
- [ ] LoadBalancer + DNS konfigurieren
- [ ] Production API Keys beschaffen und in Secrets eintragen
- [ ] Cloud Staging-Cluster deployen (mit SOPS-Secrets)

### Week 3: E2E Validierung & CI/CD
- [ ] `KUBE_CONFIG_STAGING` in GitHub Secrets eintragen (Cloud-Cluster)
- [ ] Pipeline Job 2 triggern (git push)
- [ ] Staging E2E Pass-Rate ≥95% verifizieren
- [ ] Bei Fehlern: Tests fixen oder Flaky-Tests isolieren

### Week 4: Production Preparation
- [ ] Backup-Strategie implementieren und testen
- [ ] Monitoring Stack installieren (Prometheus/Grafana)
- [ ] n8n PVC konfigurieren + Workflows importieren
- [ ] Resource Limits anpassen (höhere Replikate)
- [ ] Network Policies vollständig anwenden
- [ ] Production Terraform schreiben

### Week 5: Production Deployment (nach manueller Approval)
- [ ] Final Pre-Deployment Checklist abarbeiten
- [ ] Production Cluster provisionieren (Terraform apply)
- [ ] Secrets mit Production-Werten deployen
- [ ] Anwendung deployen
- [ ] DB-Migration durchführen
- [ ] Smoke Tests durchführen (`scripts/validate-production.sh (NEVER CREATED)`)
- [ ] Monitoring Dashboards aktivieren
- [ ] Alertmanager Rules aktivieren
- [ ] Backup Retention Policy setzen

---

## ✅ Pre-Production Checklist

### Infrastructure
- [ ] Cloud Kubernetes Cluster provisioniert (Staging & Production)
- [ ] LoadBalancer External IP verfügbar
- [ ] DNS `staging.meeting-automate.tn` → LB IP (Staging)
- [ ] DNS `meeting-automate.tn` → LB IP (Production)
- [ ] PersistentVolumes für Postgres, MinIO gebunden
- [ ] Namespaces `meeting-automation-staging` und `-prod` existieren

### Secrets & Configuration
- [ ] Alle `*-secrets.yaml` mit Production-Werten verschlüsselt (SOPS)
- [ ] Age Private Key gesichert in `~/.config/sops/age/keys.txt` (Backup!)
- [ ] `backend-config.yaml` hat `DEBUG="false"`
- [ ] `CORS_ORIGINS` enthält Production Domain nur (kein localhost)
- [ ] `ONLYOFFICE_SECRET` starkes zufälliges Secret (mind. 32 Zeichen)
- [ ] `WHATSAPP_TOKEN` vorhanden (Production Token)
- [ ] Traefik TLS Secret mit Let's Encrypt Zertifikat

### External APIs
- [ ] **Mistral AI** Production Key eingetragen
- [ ] **Gladia AI** Production Key eingetragen
- [ ] **SMTP** SendGrid/SES Production Credentials
- [ ] **Stripe** Live Secret Key + Webhooks konfiguriert
- [ ] **WhatsApp Business** Production Token aktiv

### Monitoring & Backup
- [ ] Prometheus installiert und scraping `/metrics`
- [ ] Grafana Dashboards importiert (Application, DB, AI)
- [ ] Alertmanager Rules aktiv + Test-Alert gesendet
- [ ] PostgreSQL Backup CronJob deployt
- [ ] Backup-Test erfolgreich durchgeführt (Restore verifiziert)
- [ ] MinIO Versioning aktiviert

### Security
- [ ] NetworkPolicies angewendet und getestet (`kubectl get networkpolicy`)
- [ ] Traefik Rate Limiting aktiv (50 req/s, 5 req/s auth)
- [ ] TLS Zertifikat gültig (nicht selbstsigniert)
- [ ] Keine Secrets in Klartext in Repo
- [ ] Container laufen als non-root user
- [ ] Image-Scanning (Trivy) ohne Critical/High Vulnerabilities

### Deployment Readiness
- [ ] Docker Images gepusht zu Docker Hub (mit SHA-Tagging)
- [ ] Resource Limits:
  - Backend: `memory: "2Gi"`, `cpu: "1000m"`, `replicas: 3`
  - Celery Worker: `memory: "2Gi"`, `cpu: "1000m"`, `replicas: 3`
  - PostgreSQL: `memory: "4Gi"`, `cpu: "1000m"`
- [ ] Health Checks: `/health` mit proper timeouts
- [ ] DB Migration `alembic upgrade head` erfolgreich getestet
- [ ] Initial users geseedet (admin, tech_admin, dg, manager)

### Final Checks
- [ ] DNS `meeting-automate.tn` zeigt auf Production LoadBalancer
- [ ] HTTPS erzwungen (HTTP → 301 Redirect)
- [ ] Alle Health Checks grün: `kubectl get pods -n meeting-automation-prod`
- [ ] DB-Verbindungen funktionieren
- [ ] Redis/PubSub funktioniert (Celery Tasks verarbeitet)
- [ ] n8n Workflows aktiviert (manuell importiert oder automatisch)
- [ ] OnlyOffice JWT Token Test erfolgreich
- [ ] Frontend lädt ohne Fehler (Console/Network)
- [ ] API Docs erreichbar (`/api/docs`)

---

## ❓ Offene Entscheidungen

### A) Cloud Provider
**Frage:** Welcher Cloud Provider für Staging & Production?

**Optionen:**
1. **Hetzner** (vom User erwähnt, kostengünstig, EU)
2. **AWS EKS** (global, teurer, aber robust)
3. **Google GKE** (gut integriert, einfach)
4. **Azure AKS** (Enterprise, Windows-Support)
5. **DigitalOcean** (einfach, günstig)

**Empfehlung:** Hetzner (wenn Budget wichtig) oder AWS/GCP (wenn Skalierbarkeit/Globalisierung geplant).

**Entscheidung needed before:** Infrastructure Terraform

---

### B) Staging Strategy: Local vs Cloud für CI/CD

**Current State:** Lokales Staging läuft, aber nicht CI/CD-tauglich.

**Options:**
1. **Cloud Staging einrichten** (empfohlen)
   - ✅ Echte Validierung vor Production
   - ✅ CI/CD Pipeline vollständig nutzbar
   - ✅ Realistische Netzwerk-Latenz testen
   - ✅ DNS + TLS testen
   - ❌ Kosten für Cloud-Cluster
   
2. **Nur lokales Staging, direkt Production**
   - ✅ Keine zusätzlichen Cloud-Kosten
   - ❌ Keine E2E-Validierung vor Production
   - ❌ Risiko: Unentdeckte Issues in Production
   - ❌ DNS/TLS nicht vorher getestet

**Empfehlung:** Option 1 (Cloud Staging) für Risikominimierung.

---

### C) Production API Keys Budget

**Kosten der API-Keys pro Monat (geschätzt):**
- Mistral AI: ~$50-200 (abhängig von Usage)
- Gladia AI: ~$100-300 (basierend auf Stunden Audio)
- SendGrid: ~$20-100 (ab 100k Emails/Monat)
- Stripe: 2.9% + $0.30 pro Transaktion (keine Fixkosten)
- WhatsApp Business: ~$0.005-0.07 pro Nachricht (abhängig von Land)

**Question:** Budget für Production APIs vorhanden? Wer übernimmt Kosten?

---

### D) backup Retention Policy

**Vorschlag:**
- PostgreSQL Full Dumps: 30 Tage Retention
- WAL Archive: 7 Tage Retention
- MinIO Object Versioning: Unbegrenzt (oder 90 Tage)

**Decision:** Wie lange müssen Backups aufbewahrt werden (Compliance/DSGVO)?

---

### E) Monitoring Alert Channels

**Vorschläge:**
- **Telegram Bot** (einfach, schnell)
- **Slack Webhook** (wenn Slack vorhanden)
- **Email** (als Fallback)
- **SMS** (für kritische Alerts, kostenpflichtig)

**Question:** Welche Alert-Kanäle bevorzugt das Team?

---

## 📈 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Staging E2E Pass-Rate** | ≥95% stabil | GitHub Actions Artifact |
| **Production E2E Pass-Rate** | ≥95% stabil | Smoke Tests + Full E2E (optional) |
| **Deployment Success Rate** | 100% (zero rollbacks first deploy) | Job 3 outcome |
| **MTTR (Mean Time to Recovery)** | <30 min | Rollback + Hotfix + Re-deploy |
| **Uptime** | 99.9% | Monitoring/Grafana |
| **Backup Success Rate** | 100% (keine Fehler) | CronJob logs |
| **Security Vulnerabilities** | 0 Critical/High in Trivy scans | CI/CD Scan |
| **Time to Detect Outage** | <5 min | Alertmanager Latency |

---

## 📚 Referenzen

1. `docs/STAGING_CLUSTER_SETUP_PLAN.md` – Detailliertes Staging Setup (lokal & cloud)
2. `docs/PRODUCTION_DEPLOYMENT_PLAN.md` – Vollständiger Production-Deployment-Plan
3. `docs/DEPLOYMENT.md` – Deployment Guide (docker-compose + K8s)
4. `docs/DEPLOYMENT_PIPELINE_STATUS_2026-04-05.md` – Pipeline Status & Issues
5. `docs/E2E_VALIDATION_REPORT_2026-04-05.md` – E2E Test Results (97%)
6. `PROTOCOL_PART_27_SECRET_MANAGEMENT_PHASE_1.md` – SOPS/age Secrets
7. `PROTOCOL_PART_35_KUBERNETES_STABILITY_AND_RESOURCES.md` – Ressourcen Limits
8. `PROTOCOL_PART_31_TRAEFIK_RATE_LIMITING.md` – Traefik als API Gateway
9. `PROTOCOL_PART_33_SSL_TLS_ENCRYPTION.md` – TLS Implementation
10. `PROJECT_STATUS.md` – Gesamt-Projektstatus & Roadmap

---

## 💡 Nächste Schritte (Was jetzt?)

### Sofort (Heute/Diese Woche):
1. ✅ **Cloud Provider wählen** und Terraform-Config beginnen
2. ✅ **Production API Keys** bei Anbietern beantragen (Mistral, Gladia, SMTP, Stripe, WhatsApp)
3. ✅ `backend-secrets.yaml` reviewen: Fehlende Keys ergänzen
4. ✅ Backup-Skript `scripts/backup-db.sh` implementieren

### Kurzfristig (Nächste 2 Wochen):
5. ⏳ Cloud Staging-Cluster provisionieren
6. ⏳ `KUBE_CONFIG_STAGING` in GitHub Secrets eintragen
7. ⏳ Pipeline Job 2 triggern und Ergebnisse prüfen
8. ⏳ Monitoring Stack (Prometheus/Grafana) installieren
9. ⏳ n8n PVC + Workflow-Persistence konfigurieren

### Vor Production (1-2 Wochen vor Go-Live):
10. ⏳ Production Terraform schreiben und anwenden
11. ⏳ Production Secrets mit echten Keys verschlüsseln
12. ⏳ Full Staging E2E mit Cloud-Cluster laufen lassen
13. ⏳ Backup Restore-Test durchführen
14. ⏳ Pre-Deployment Checklist komplett abhaken

---

**Bericht erstellt:** 2026-04-05  
**Nächste Review:** Nach Cloud-Staging-Setup oder vor Production-Deployment
