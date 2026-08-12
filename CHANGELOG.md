# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.91.0] — 2026-08-12

### Added
- **Velero Pre-Deploy-Backup (CI/CD)**: `deploy-production.yml` erstellt automatisch Velero Backup vor jedem Production-Deploy — Name: `pre-deploy-<sha>-<timestamp>`, TTL 14 Tage
- **MinIO PVC Alerts (Prometheus)**: `MinIOPvcHighUsage` (80% Warning) + `MinIOPvcCriticalUsage` (90% Critical) für Staging + Production
- **Velero Backup Size Alert**: `VeleroBackupSizeHigh` (>30GB Warning) nur für Staging
- **VELERO_BACKUP_PLAN.md Section 15**: Staging Disk-Pressure Lektionen (local-path erzwingt keine Limits, Prometheus erzeugt 44GB aus 5Gi PVC)
- **VELERO_BACKUP_PLAN.md Section 16**: Recovery-Verfahren (Kopia-Repository Reset) — 8-Schritte Prozess mit Quick Reference Tabelle
- **VELERO_BACKUP_PLAN.md Section 17**: Roadmap — CI/CD Pre-Deploy-Backup + Externes S3 + Priorisierte offene Punkte

### Changed
- **Staging Velero Retention**: TTL von 168h (7 Tage) auf 72h (3 Tage) gekürzt — spart Speicher auf 183GB Disk
- **Staging Velero Schedule**: `excludedNamespaces: [monitoring]` + `labelSelector: app in (minio-staging,postgres-staging)` — nur 20Gi PVCs statt 43Gi
- **Staging Velero Helm Upgrade**: REVISION 5 mit `deployNodeAgent=true` (DaemonSet war verschwunden)

### Fixed
- **Staging Node-Agent verschwunden**: Helm `--reuse-values` hat DaemonSet nicht wiederhergestellt — manuell per Helm Upgrade mit `deployNodeAgent=true` wiederhergestellt
- **Staging Grafana im Completed-State**: 11 alte Pods im Succeeded/Failed State — gelöscht + Deployment rollout restart
- **VELERO_BACKUP_PLAN.md Schedule-Patch Hinweis**: Dokumentiert dass Helm keine bestehenden Schedules aktualisiert — manueller Patch erforderlich

## [1.90.0] — 2026-08-11

### Fixed
- **🔴 CRITICAL — pg_dump Backup Root Cause (Production)**: CronJob hatte HARDCODED `TIMESTAMP=20260811-114339` → jeder Lauf überschrieb dieselbe Datei → 20-Byte GZip-Header (5 defekte Backups Aug 6-11). FIX: `TIMESTAMP=$(date +%Y%m%d-%H%M%S)` für dynamischen Timestamp. **NetworkPolicy-Regel für `postgres-backup` zusätzlich hinzugefügt** (war nicht die Root Cause, aber Good Practice).
- **🔴 CRITICAL — OnlyOffice Production ConfigMap**: ConfigMap wurde gelöscht aber nie wiederhergestellt → `TypeError: Cannot set properties of undefined (setting 'allowPrivateIPAddress')` + nginx Start fehlgeschlagen. FIX: Korrektes `local.json` mit `request-filtering-agent` Sektion + korrekte Secrets + `ds-docservice.conf` wiederhergestellt.
- **OnlyOffice Production Secret Mismatch**: `local.json` hatte `production-onlyoffice-secret-jwt-key-2026`, aber Deployment Env hatte `tHjRho7Mrgicb9g09trClzCPt9X5OI48ZIfGWILLnkQ` → Browser Auth fehlgeschlagen. FIX: Secrets synchronisiert.
- **OnlyOffice Production Image unpinned**: `onlyoffice/documentserver:latest` → `onlyoffice/documentserver:9.4.0` (wie Staging) — verhindert unvorhersehbare Updates.
- **OnlyOffice CI/CD Drift**: Manuelle Prod-Änderungen (ConfigMap + Image) nicht in Git → nächstes Deploy hätte korrekten Zustand überschrieben. FIX: YAML-Dateien in Git aktualisiert (`infrastructure/kubernetes/production/onlyoffice-custom-config.yaml` + `onlyoffice-deployment.yaml`).
- **Backup CronJob pg_dump Image**: `postgres:15-alpine` → `postgres:18-alpine` (Staging + Production) — PG 15 Dump inkompatibel mit PG 18 Restore
- **Backup CronJob DNS (Staging)**: Hardcoded IP `10.43.101.189` → `meeting-db-rw...svc.cluster.local` — pg_dump fehlgeschlagen seit Tagen
- **Ephemeral Storage Limits**: CronJobs mit `limits: 2Gi`, `requests: 200Mi` hinzugefügt
- **Longhorn Default SC (Staging)**: `is-default-class: false` — nur `local-path` als Default
- **Longhorn Default SC (Production)**: `is-default-class: false` — nur `local-path` als Default
- **SENTINEL_MODEL_URL (Staging)**: Fehlende ConfigMap-Entry hinzugefügt — Sentinel LLM funktioniert jetzt in Staging

### Added
- **Velero Monitoring (beide Cluster)**: ServiceMonitor + PrometheusRule (4 Alerts: BackupFailed, TooOld, DurationHigh, PartialFailure)
- **Velero Daily Schedule (Production)**: `daily-backup` mit 14d TTL
- **Docs Audit**: 174/174 MD-Dateien verifiziert, ~90 broken references gefixt (n8n IDs, Port 3000, E2E_MODE, stale workflow refs)
- **Staging vs Production Audit**: Vergleichstabelle + Fix-Vorschläge (`docs/STAGING_VS_PRODUCTION_AUDIT_2026-08-11.md`)
- **Velero FSB Backup Plan**: Scoped Backup + Restore-Test + Monitoring dokumentiert (`docs/VELERO_BACKUP_PLAN.md`)

### Changed
- **CI/CD Pipeline**: `ci.yml` Path-Filter um `.github/workflows/` erweitert
- **deploy-production.yml**: SSH timeout `10m → 20m`, Smoke-Test Port dynamisch (18080→19080), kein Rollback bei Fehler
- **deploy-staging.yml**: Helm-Values + LiveKit-Deployment Skip-Regeln korrigiert

## [1.89.0] — 2026-08-10

### Fixed
- **CI/CD Helm Timeout**: `--timeout 5m → 10m` für LiveKit Egress/Server Helm upgrades
- **CI/CD Smoke Test**: Zombie port-forward Cleanup + dynamischer Port + kein Rollback bei Fehler
- **CI/CD Codecov**: `token: ${{ secrets.CODECOV_TOKEN }}` hinzugefügt
- **Duplicate Workflows**: `backend-ci.yml` + `frontend-ci.yml` deaktiviert (waren Duplikate von `ci.yml`)

### Added
- **Docs Audit Summary**: `docs/DOCS_AUDIT_SUMMARY_2026-08-10.md` — vollständige Fehleranalyse aller 174 Docs
- **AGENTS.md Update**: CI/CD Sektion, n8n Workflow IDs, Frontend Port 3001, fehlende Docs Referenzen

### Changed
- **88 Docs-Dateien**: Stale Referenzen bereinigt (E2E_MODE→E2E_TEST, alte n8n IDs, Port 3000→3001, backend-ci.yml refs)

## [1.88.0] — 2026-08-09

### Fixed
- **deploy-production.yml SSH Timeout**: `command_timeout: 20m` für lange Deploys
- **deploy-production.yml Smoke Test**: Port-Zombie Cleanup + Port 19080 statt 18080
- **deploy-production.yml Rollback entfernt**: Smoke-Test Fehler = WARNING, kein automatischer Rollback

### Changed
- **ci.yml Path Filter**: `.github/workflows/` hinzugefügt — Workflow-Änderungen lösen CI aus
- **LiveKit Egress Deploy**: `helm upgrade --install` + `kubectl rollout status` (statt raw YAML apply)

## [1.87.0] — 2026-08-08

### Added
- **Velero Installation (Staging)**: Helm chart v12.1.0, daily-backup schedule, MinIO backend
- **Velero Installation (Production)**: Helm chart v12.1.0, FSB aktiviert, daily-backup schedule
- **Velero First FSB Backup (Production)**: 28.7GiB COMPLETED mit 7/7 PVCs
- **Velero Restore-Test (Production)**: Namespace-Mapping restore in `restore-test` — 179 Items, 7/7 PVCs, MinIO-Daten wiederhergestellt

### Fixed
- **LiveKit Egress Pending Pod**: hostNetwork Port-Konflikt durch alte Pods — manuelle Bereinigung erforderlich

## [1.86.0] — 2026-08-07

### Added
- **LiveKit CPU Fix**: CPU Limit `500m → 1000m` für stability
- **LiveKit TURN Config**: UDP/TCP Fallback dokumentiert
- **LiveKit Force Relay**: `iceTransportPolicy: relay` Versuche dokumentiert (später entfernt)

### Fixed
- **LiveKit 15s Disconnect Root Cause**: WebSocket Timeout + peerConnectionTimeout Analyse
- **LiveKit Relay Reconnect Loop**: TURN-Client Fix dokumentiert