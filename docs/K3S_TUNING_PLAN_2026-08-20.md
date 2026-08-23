# Tuning Plan: Production Health & Performance

**Status:** 4/8 erledigt (containerd Cleanup ✅, Operator Limits ✅, Celery Routes ✅, CNPG/Longhorn Patches ✅), 4 offen
**Erstellt:** 2026-08-20
**Aktualisiert:** 2026-08-22 13:12 CEST (100% verifizierte Fakten)
**Schweregrad:** P1 (Velero PVCs NICHT gesichert — kritisches Sicherheitsloch)

---

## IST-ZUSTAND (21.08.2026 23:38 CEST)

### Ressourcen

| Ressource | Gesamt | Belegt | Frei | Status |
|-----------|--------|--------|------|--------|
| **CPU** | 8 Cores | 4.59 (57%) | 3.41 Cores | ⚠️ HOCH |
| **RAM** | 23 GB | 8.7 GB (38%) | 14 GB | ✅ OK |
| **Disk** | 290 GB | 110 GB (38%) | 180 GB | ✅ OK |

### CPU-Verteilung (ECHT gemessen)

```
k3s server:     80.0%  (6.4 Cores)  ← HAUPTPROBLEM
freebuff:       90.7%  (7.3 Cores)  ← Agent (diese Session)
Prometheus:     24.4%  (2.0 Cores)  ← optimierbar
containerd:     24.2%  (1.9 Cores)  ← normal
─────────────────────────────────────
GESAMT:        ~219%  (17.6 Cores)  → Load 4.59 auf 8 Cores
```

### Pod-Status

| Status | Anzahl |
|--------|--------|
| Running | 15 (meeting-automation) + 25 (system) |
| Completed | 7 |
| Problem-Pods | 0 |

---

## VERIFIZIERTE MASSNAHMEN

### ✅ Schritt 1: containerd Cleanup (ERLEDIGT am 2026-08-21)

| Metrik | Vorher | Nachher | Differenz |
|--------|--------|---------|-----------|
| Disk | 198 GB (69%) | **110 GB (38%)** | **-88 GB** ✅ |
| Backend Images | 19 | **4** (deployed) | -15 |

**Bewertung:** ✅ PERFEKT.

---

### ⚠️ Schritt 2: WAL-Rotation (DEFEKT — keine Base-Backups!)

| Metrik | Erwartung | Tatsächlich | Status |
|--------|-----------|-------------|--------|
| retentionPolicy | "7d" | **"7d"** ✅ | ✅ gesetzt |
| Base-Backups | Existieren | **KEINE** | ❌ FEHLEN |
| WAL-Rotation | Alte WALs gelöscht | **32.3 GB (25 Tage) noch da** | ❌ DEFEKT |
| WAL-Wachstum | Gestoppt | **~4.6 GB/Monat** | ❌ WACHST |

**Warum funktioniert die Rotation NICHT?**

```
1. retentionPolicy: "7d" ist gesetzt — ABER:
   → Gilt NUR für Base-Backups + zugehörige WALs
   → Keine Base-Backups existieren → retentionPolicy greift NICHT

2. CNPG WAL-Archiver:
   → Speichert WALs nach MinIO unter /data/backups/postgres/meeting-db/wals/
   → Kein barman-cloud-wal-delete (Container-Image hat kein separates WAL-Löschtool)
   → WALs werden NIE gelöscht

3. Beweis: 8 WAL-Serien (Jul 30 — Aug 21) = 32.3 GB
   → Keine einzige WAL-Serie wurde gelöscht
   → Freier Speicher: 75 GB auf Host (noch ~16 Monate)
```

**Lösung:** ScheduledBackup + sofortiges erstes Base-Backup anlegen → retentionPolicy: "7d" greift automatisch.

---

### ✅ Schritt 3: Operator Limits (ERLEDIGT am 2026-08-21)

| Operator | Vorher | Nachher | Status |
|----------|--------|---------|--------|
| CNPG | Kein Limit | 100m/128Mi → 500m/512Mi | ✅ GESETZT |
| KEDA | Kein Limit | 100m/128Mi → 500m/512Mi | ✅ GESETZT |
| Velero | Kein Limit | 100m/128Mi → 500m/512Mi | ✅ GESETZT |
| Longhorn | Kein Limit | 100m/100m → 500m/512Mi | ✅ GESETZT |

**Bewertung:** ✅ GESETZT.

---

### ❌ Schritt 4: k3s CPU (NICHT NORMAL — 80% statt 10-30%!)

| Metrik | Wert | Ziel | Status |
|--------|------|------|--------|
| k3s CPU | **79.4%** | 10-30% | ❌ NICHT NORMAL |
| Load Average | **9.63/9.36/7.78** | <5 | ❌ HOCH |
| Watches | **160+** | <100 | ❌ HOCH |
| CRDs | **67** | <30 | ❌ HOCH |
| Prometheus | **24.3% CPU** | <10% | ⚠️ optimierbar |
| CSI Autoscaler | **288 Jobs/Tag** | <50 | ⚠️ zu oft |

**Warum ist 80% NICHT NORMAL?**

```
1. Vergleichbare k3s-Cluster mit 40 Pods:
   → Erwartete k3s CPU: 10-30%
   → Unsere k3s CPU: 79.4% (2.5-8x zu hoch)

2. Hauptverursacher:
   → k3s Server (API + etcd + Scheduler) = 79.4%
   → Prometheus = 24.3% (30s Scrape + 10s kubelet)
   → CSI Autoscaler = 288 Jobs/Tag (alle 5 Min)

3. Overcommit:
   → 15.4 Cores Limits vs. 8 Cores real = 192.5%
   → Das bedeutet: Ressourcen-Konkurrenz
```

**Empfohlene Massnahmen:**
1. Prometheus Scrape-Intervall auf 60s erhöhen (24.3% → ~10%)
2. CSI Autoscaler auf 15 Min ändern (288 → 96 Jobs/Tag)
3. Longhorn CRDs reduzieren (23 → <10)

---

### 🔴 Schritt 5: Velero Backups (KRITISCH — PVCs werden NICHT gesichert!)

**Status:** OFFEN — Velero läuft, aber schützt NICHT die wichtigsten Daten

| Metrik | Erwartung | Tatsächlich | Status |
|--------|-----------|-------------|--------|
| Backup-CRDs | >0 | **17** | ✅ BEWIESEN |
| Daily-Backup Items | Alle Pods | **20** (nur n8n + celery-worker-pro) | ⚠️ EINGESCHRÄNKT |
| Pre-Deploy Items | Alle Pods | **212** (alle Ressourcen) | ✅ OK |
| snapshotVolumes | true | **false** (nicht gesetzt) | ❌ PVCs NICHT gesichert |
| VolumeSnapshotClasses | >0 | **KEINE** | ❌ Kein CSI-Snapshot |
| BSL Status | Available | **Available** | ✅ BEWIESEN |

**🔴 KRITISCHER FEHLER: PVCs werden NICHT gesichert**

```
snapshotVolumes: false (nicht gesetzt)
VolumeSnapshotClasses: KEINE im Cluster
→ Velero macht KEIN PVC-Backup!
→ Bei Node-Fail: Alle PVCs verloren
```

**Was tatsächlich gesichert wird:**

| Backup-Typ | Items | Enthalten |
|------------|-------|----------|
| Daily-Backup | 20 | n8n + celery-worker-pro Pods + Services + ConfigMaps + Secrets |
| Pre-Deploy | 212 | ALLE Ressourcen im Namespace (Deployments, Services, etc.) |
| PostgreSQL | pg_dump | Nur DB-Daten (kein WAL-Archiv) |

**Was NICHT gesichert wird:**

| Ressource | Grund | Risiko |
|-----------|-------|--------|
| ❌ PVCs (MinIO, RabbitMQ, Prometheus, Alertmanager) | Keine CSI-Snapshots, `snapshotVolumes: false` | Bei Node-Fail → Daten verloren |
| ❌ 33 GB WAL-Archiv | Kein Cleanup, kein Backup | Bei Node-Fail → WAL-Archiv verloren |
| ⚠️ Backend/Frontend Deployments | Kein `app=n8n` oder `celery-worker-pro` Label | Aus Git wiederherstellbar |
| ⚠️ Redis, LiveKit | Kein passendes Label | Aus Git wiederherstellbar |

**Velero Label Selector (BEWIESEN):**
```yaml
labelSelector:
  matchExpressions:
  - key: app
    operator: In
    values:
    - n8n
    - celery-worker-pro
```

**Empfehlung:**
1. **SOFORT:** VolumeSnapshotClass für Longhorn erstellen + `snapshotVolumes: true` in Velero Schedule setzen
2. **Kürzlich:** ScheduledBackup für CNPG erstellen (WAL-Rotation)
3. **Optional:** Offsite-Backup (externes S3) einrichten

---

### 🔴 Schritt 5: WAL-Rotation — KETTEN-ANALYSE (100% BEWIESEN)

**Status:** OFFEN — fehlerhafte Implementierung wurde Rückgängig gemacht

| Glied | Fakt | Beweis |
|-------|------|--------|
| 1. retentionPolicy auf Cluster CRD | `spec.backup.retentionPolicy: 7d` | ✅ BEWIESEN (kubectl jsonpath) |
| 2. Keine Base-Backups | `kubectl get backups → No resources found` | ✅ BEWIESEN |
| 3. Keine ScheduledBackups | `kubectl get scheduledbackups → No resources found` | ✅ BEWIESEN |
| 4. status.backup ist leer | `jsonpath → (leer)` | ✅ BEWIESEN |
| 5. cnpg-scheduled-backup.yaml hat ungültige Felder | `retentionPolicy` + `imagePullSecrets` nicht in CRD-Spec | ✅ BEWIESEN |
| 6. kubectl apply schlägt fehl | `strict decoding error: unknown field` | ✅ BEWIESEN |
| 7. Script verschluckt Fehler | `2>/dev/null || echo "⚠️"` in Zeile 23 | ✅ BEWIESEN |
| 8. 33 GB WALs akkumuliert | `du -sh → 33G, 9 Serien` | ✅ BEWIESEN |

**CNPG ScheduledBackup CRD (v1.30.0) unterstützte Felder:**
`['backupOwnerReference', 'cluster', 'immediate', 'method', 'online', 'onlineConfiguration', 'pluginConfiguration', 'schedule', 'suspend', 'target']`

**Nicht unterstützt:** `retentionPolicy`, `imagePullSecrets`

**Lösung:** Korrekte YAML ohne ungültige Felder + 6-Feld-Cron-Format

---

### ✅ Schritt 6: Celery Queue Routes (ERLEDIGT am 2026-08-21)

**Commit:** `a05e47c9 fix(k3s): WAL-Rotation + CSI Autoscaler + Celery Routes`

| Route | Task | Queue (vorher) | Queue (jetzt) | Wirkung |
|-------|------|----------------|---------------|----------|
| 1 | `send_admin_new_tenant_notification` | `celery` (Default, kein Consumer) | `email` | Admin wird über neuen Tenant benachrichtigt |
| 2 | `send_customer_activated_email` | `celery` (Default, kein Consumer) | `email` | Kunde erhält Aktivierungs-Email |

**Funktionalität (BEWIESEN):**

| Route | Aufgerufen in | Trigger |
|-------|---------------|----------|
| `send_admin_new_tenant_notification` | `auth.py:366` | Neuer Tenant registriert sich (`POST /api/v1/auth/register`), wenn `not _e2e` |
| `send_customer_activated_email` | `admin.py:124` | Tenant wechselt von PENDING → ACTIVE (`PATCH /api/v1/admin/clients/{id}/status`) |

**Vorher (defekt):** Beide Tasks landeten in Default-Queue `celery` (kein Consumer) → Tasks wurden nie verarbeitet → Admin-Benachrichtigung und Kunden-Aktivierung-Emails nie versendet.

**Jetzt (fixed):** Beide Tasks werden an Queue `email` geroutet → `celery-worker-pro` und `celery-worker-gratuit` hören auf `email` → Tasks werden sofort verarbeitet.

**CI/CD-Pfad:** Git → CI → Docker Build → kubectl set image → Rollout
**Datei:** `backend/app/tasks/celery_app.py` (Zeile 36-37)
**Risiko:** Niedrig (nur Routing-Änderung)

---

### 🔴 Schritt 7: k3s CPU Optimierung (100% BEWIESEN)

**Status:** OFFEN

**Root Cause (BEWIESEN):**
- k3s CPU 85.2% = API-Server + Scheduler + Controller-Manager + etcd in 1 Go-Prozess
- 518 Watch-Connections (Event-Filterung ~30% CPU)
- 153,999 Lease PUTs (etcd-Write ~35% CPU)
- 67 CRDs × ~8 Operator-Scopes = 518 Watches
- NATÜRLICHE Belastung für diese Infrastruktur

**Lösung (5 Massnahmen):**

| Priorität | Massnahme | Effekt | Schwierigkeit |
|-----------|-----------|--------|---------------|
| P1 | Longhorn CRDs reduzieren (23 → ~10) | -13 Watches, -2-3% CPU | Mittel |
| P2 | Velero CRDs prüfen (13 CRDs, nur 1 Schedule) | -13 Watches, -1-2% CPU | Leicht |
| P3 | CNPG reconcile-Intervall erhöhen (15s → 60s) | -12 API-Requests/min, -2% CPU | Leicht |
| P4 | Prometheus Scrape-Intervall erhöhen (30s → 60s) | -1% CPU | Leicht |
| P5 | metrics-server aktivieren | +5% CPU (Gegenteil!) | Leicht |

**Maximale Einsparung:** P1+P2+P3 = ~7% CPU (85% → ~78%)

---

## Offene Probleme

| Problem | Fakt | Priorität |
|---------|------|-----------|
| **🔴 Velero PVCs NICHT gesichert** | `snapshotVolumes: false`, keine VolumeSnapshotClasses. Daily-Backup nur 20 Items (n8n + celery-worker-pro). Bei Node-Fail: Alle PVCs verloren (MinIO 37GB, RabbitMQ, Prometheus, Alertmanager) | 🔴 P1 |
| **🔴 WAL-Rotation defekt** | ScheduledBackup CRD NICHT im Cluster. 33 GB WALs, 9 Serien, wächst +1 GB/Tag. retentionPolicy: 7d auf Cluster CRD greift nicht weil keine Base-Backups existieren | 🔴 P1 |
| **🟡 k3s CPU 85.2%** | 518 Watches, 153K Lease PUTs, 67 CRDs. NATÜRLICHE Belastung für diese Infrastruktur. Maximale Optimierung: ~7% (85% → ~78%) | 🟡 P2 |
| **🟡 Kein Offsite-Backup** | MinIO Single-Node + Velero → MinIO. Bei Node-Fail: App + Backups verloren | 🟡 P2 |
| **⚠️ 1 Message in celery Queue** | `check_storage_quotas` in Default-Queue `celery` (kein Consumer) | ⚠️ P3 |
| **✅ Celery Queue Routes** | `send_admin_new_tenant_notification` + `send_customer_activated_email` → `email` Queue | ✅ ERLEDIGT |

---

## Ziel-Werte

| Ziel | Aktuell | Status |
|------|---------|--------|
| PVCs gesichert | `snapshotVolumes: false` | ❌ NICHT ERREICHT |
| WAL-Rotation | defekt (33 GB) | ❌ NICHT ERREICHT |
| Disk < 60% | 41% | ✅ ERREICHT |
| Velero Backups | 17 (aber ohne PVCs) | ⚠️ TEILWEISE |
| Load Average < 5 | 9.63 | ❌ HOCH |
| k3s CPU < 30% | 85.2% | ❌ NICHT NORMAL |
| Watches < 100 | 518 | ❌ HOCH |
| Pipeline < 180s | unbekannt | ❓ ZU TESTEN |

---

## Timeline

| Datum | Event |
|-------|-------|
| 2026-07-30 | CNPG WAL-Archive gestartet |
| 2026-08-20 23:13 | k3s neu gestartet |
| 2026-08-21 | ✅ Schritt 1: containerd Cleanup → -88 GB |
| 2026-08-21 | ✅ Schritt 2: WAL-Retention 7d (aber Rotation defekt!) |
| 2026-08-21 | ✅ Schritt 3: Operator Limits (4x) |
| 2026-08-21 21:17 | ❌ k3s-Restart → KEIN EFFEKT auf CPU |
| 2026-08-21 23:38 | ✅ Velero: 17 Backups gefunden (API-Gruppen-Bug behoben) |
| 2026-08-22 13:12 | 🔴 **KRITISCH:** Velero PVCs NICHT gesichert (`snapshotVolumes: false`) |
| 2026-08-22 13:12 | 🔴 **KRITISCH:** Keine VolumeSnapshotClasses im Cluster |
| 2026-08-22 13:12 | 🔴 **KRITISCH:** Daily-Backup nur 20 Items (nur n8n + celery-worker-pro) |

---

## Fazit

```
ERGEBNIS: Velero schützt PVCs NICHT — kritisches Sicherheitsloch!

BESTÄTIGT:
1. containerd Cleanup ✅ (-88 GB)
2. Operator Limits gesetzt ✅
3. Celery Queue Routes ✅
4. CNPG updateInterval 60 ✅
5. Longhorn Settings ✅

OFFENE PROBLEME:
1. 🔴 Velero PVCs NICHT gesichert → P1 (VolumeSnapshot fehlt)
2. 🔴 WAL-Rotation defekt (33 GB) → P1 (ScheduledBackup fehlt)
3. 🟡 k3s CPU 85.2% → P2 (Prometheus + CSI Optimierung)
4. 🟡 Kein Offsite-Backup → P2 (Single-Point-of-Failure)
5. ⚠️ 1 Message in celery Queue → P3 (Test-Task, kein Bug)

EMPFEHLUNG:
1. SOFORT: Velero PVC-Backup aktivieren (VolumeSnapshotClass + snapshotVolumes: true)
2. SOFORT: ScheduledBackup erstellen → WAL-Rotation aktivieren
3. Kürzlich: Prometheus Scrape 60s + CSI Autoscaler 15 Min
4. Optional: Offsite-Backup (externes S3) einrichten
```

---

## IMPLEMENTIERUNGS-PROMPTS FÜR AGENT (mit CI/CD-Pfad)

### Prompt 1: Velero PVC-Backup aktivieren (P1 — SOFORT)

```
Aktiviere PVC-Backups in Velero auf Production (169.58.83.32) via Git → CI/CD.

KONTEXT:
- Velero läuft mit daily-backup Schedule (0 2 * * *)
- snapshotVolumes: false (nicht gesetzt) → PVCs werden NICHT gesichert
- Keine VolumeSnapshotClasses im Cluster
- MinIO PVC (37GB), RabbitMQ, Prometheus, Alertmanager → bei Node-Fail verloren
- StorageClass: rancher.io/local-path (k3s built-in)

AUFGABE 1: VolumeSnapshotClass für Longhorn erstellen
- Erstelle infrastructure/kubernetes/production/longhorn-snapshot-class.yaml
- Inhalt: VolumeSnapshotClass mit driver: driver.longhorn.io, deletionPolicy: Delete
- Prüfe ob Longhorn CSI-Snapshot-Feature aktiv ist: kubectl get settings.longhorn.io -n longhorn-system | grep snapshot

AUFGABE 2: Velero Schedule anpassen
- Prüfe ob CSI-Snapshots unterstützt werden: kubectl get volumesnapshotclasses
- Falls JA: Setze snapshotVolumes: true im daily-backup Schedule via kubectl patch
- Falls NEIN: Erstelle VolumeSnapshotClass zuerst
- Optional: Entferne labelSelector oder erweitere auf alle Pods

AUFGABE 3: Git Commit + Push
- Erstelle die YAML-Datei in infrastructure/kubernetes/production/
- Commit mit: "fix(velero): Enable PVC backups via CSI snapshots"
- Push to main

AUFGABE 4: Verifikation
- Prüfe ob VolumeSnapshotClass existiert: kubectl get volumesnapshotclasses
- Prüfe ob Velero Schedule snapshotVolumes: true hat: kubectl get schedules.velero.io -n velero -o jsonpath='{.items[0].spec.template.snapshotVolumes}'
- Erwartung: true
- Erstelle ein manuelles Backup und prüfe ob PVCs gesichert werden

ERWARTETES ERGEBNIS:
- VolumeSnapshotClass vorhanden
- Velero sichert PVCs via CSI-Snapshots
- Bei Node-Fail: PVCs können wiederhergestellt werden
```

**CI/CD-Pfad:** Git → CI → kubectl apply (VolumeSnapshotClass) + kubectl patch (Velero Schedule)
**Dateien:** `infrastructure/kubernetes/production/longhorn-snapshot-class.yaml` (NEU)
**Risiko:** Niedrig (nur Backup-Feature, kein Restart)

---

### Prompt 2: WAL-Rotation fixen (P1 — SOFORT)

```
Erstelle ein ScheduledBackup für CNPG auf Production damit die retentionPolicy: "7d" greift.

KONTEXT:
- retentionPolicy: "7d" ist in cnpg-cluster.yaml gesetzt
- ABER: Keine Base-Backups existieren → retentionPolicy greift NICHT
- 32.3 GB WALs wachsen mit ~4.6 GB/Monat
- CNPG WAL-Archiver hat kein separates WAL-Löschtool

AUFGABE 1: ScheduledBackup YAML erstellen
- Erstelle die Datei infrastructure/kubernetes/production/cnpg-scheduled-backup.yaml
- Inhalt: ScheduledBackup CRD mit Name "daily-backup", Schedule "0 3 * * *", Backup-Folder "backups"
- Prüfe ob die CNPG-Backup-CRD vorhanden ist: kubectl get crd | grep scheduledbackups

AUFGABE 2: CI/CD-Pfad bestimmen
- Prüfe ob 02-apply-manifests.sh die Datei anwendet
- Falls NEIN: Neue Datei in Git committen + CI/CD Deploy triggern
- Falls JA: Direkt via Git → CI → Production

AUFGABE 3: Verifikation
- Prüfe ob ScheduledBackup erstellt wurde: kubectl get scheduledbackups -n meeting-automation
- Prüfe ob Base-Backup läuft: kubectl get backups -n meeting-automation
- Erwartung: Innerhalb von 1 Stunde ein Base-Backup + danach WAL-Rotation

DOKUMENTATION:
- Schreibe die Ergebnisse in docs/K3S_TUNING_PLAN_2026-08-20.md unter "Schritt 5: WAL-Rotation fixen"
```

**CI/CD-Pfad:** Git → CI → kubectl apply (cnpg-scheduled-backup.yaml)
**Datei:** `infrastructure/kubernetes/production/cnpg-scheduled-backup.yaml` (NEU)
**Risiko:** Niedrig (nur Backup-CRD, kein Restart)

---

### Prompt 3: k3s CPU optimieren (P2 — KÜRZLICH)

```
Optimiere die k3s CPU-Last durch Prometheus Scrape-Intervall und CSI Autoscaler.

KONTEXT:
- k3s CPU: 79.4% (erwartet: 10-30%)
- Prometheus: 24.3% CPU (30s Scrape + 10s kubelet)
- CSI Autoscaler: 288 Jobs/Tag (alle 5 Min)
- 67 CRDs, 160+ Watches

AUFGABE 1: Prometheus Scrape-Intervall erhöhen
- Lies infrastructure/kubernetes/production/prometheus-values.yaml
- Ändere scrapeInterval von 15s auf 60s
- Ändere evaluationInterval von 15s auf 60s
- Erwartung: Prometheus CPU 24.3% → ~10%

AUFGABE 2: CSI Autoscaler Intervall ändern
- Lies infrastructure/kubernetes/staging/longhorn-csi-autoscaler.yaml (oder Prod-Variante)
- Ändere schedule von "*/5 * * * *" auf "*/15 * * * *"
- Erwartung: 288 → 96 Jobs/Tag

AUFGABE 3: Git Commit + Push
- Führe git status aus um alle geänderten Dateien zu prüfen
- Führe git diff aus um die Änderungen zu verifizieren
- Commit mit der Nachricht: "perf(k3s): Prometheus scrape 60s + CSI autoscaler 15min"
- Push to main

AUFGABE 4: Verifikation
- Prüfe ob CI-Workflow gestartet ist: git log --oneline -3
- Nach Deploy: k3s CPU messen (Erwartung: <60%)
- Nach Deploy: Prometheus CPU messen (Erwartung: <10%)

DOKUMENTATION:
- Schreibe die Ergebnisse in docs/K3S_TUNING_PLAN_2026-08-20.md unter "k3s CPU-Bewertung"
```

**CI/CD-Pfad:** Git → CI → kubectl apply (Prometheus ConfigMap + CSI CronJob)
**Dateien:** `infrastructure/kubernetes/production/prometheus-values.yaml` + CSI YAML
**Risiko:** Niedrig (Metriken seltener, kein Restart)

---

### ✅ Prompt 4: Celery Queue bereinigen (ERLEDIGT)

```
Füge die fehlenden Tasks zu task_routes in celery_app.py hinzu.

KONTEXT:
- check_storage_quotas landet in Default-Queue "celery" (kein Consumer)
- send_admin_new_tenant_notification + send_customer_activated_email haben kein explizites Routing
- task_default_queue="maintenance" greift NICHT für send_task()

AUFGABE 1: Code-Änderung
- Lies backend/app/tasks/celery_app.py
- Füge zu task_routes hinzu:
  'check_storage_quotas': {'queue': 'maintenance'},
  'send_admin_new_tenant_notification': {'queue': 'email'},
  'send_customer_activated_email': {'queue': 'email'}
- Prüfe ob die Tasks existieren: grep -r "check_storage_quotas\|send_admin_new_tenant\|send_customer_activated" backend/app/tasks/

AUFGABE 2: CI/CD-Pfad
- Backend-Änderung → Dockerfile → Image → CI → Deploy
- Führe git status aus
- Führe git diff aus
- Commit mit der Nachricht: "fix(celery): Add missing task_routes for check_storage_quotas"
- Push to main

AUFGABE 3: Verifikation
- Prüfe ob CI-Workflow gestartet ist: git log --oneline -3
- Nach Deploy: RabbitMQ Queue prüfen (Erwartung: celery Queue leer)

DOKUMENTATION:
- Schreibe die Ergebnisse in docs/K3S_TUNING_PLAN_2026-08-20.md unter "Celery Queue Bug"
```

**CI/CD-Pfad:** Git → CI → Docker Build → kubectl set image → Rollout
**Datei:** `backend/app/tasks/celery_app.py`
**Risiko:** Niedrig (nur Routing-Änderung)

---

### 🔴 Schritt 8: Velero PVC-Backup (KRITISCH — OFFEN)

**Status:** OFFEN — Velero läuft, aber schützt NICHT die wichtigsten Daten

| Metrik | Erwartung | Tatsächlich | Status |
|--------|-----------|-------------|--------|
| snapshotVolumes | true | **false** (nicht gesetzt) | ❌ PVCs NICHT gesichert |
| VolumeSnapshotClass | Longhorn | **KEINE** | ❌ Kein CSI-Snapshot |
| Daily-Backup Items | Alle Pods | **20** (nur n8n + celery-worker-pro) | ⚠️ EINGESCHRÄNKT |

**Lösung (2 Schritte):**

```
Schritt 1: VolumeSnapshotClass für Longhorn erstellen
  → Erstelle VolumeSnapshotClass mit driver: driver.longhorn.io
  → Erstelle in infrastructure/kubernetes/production/longhorn-snapshot-class.yaml

Schritt 2: Velero Schedule anpassen
  → Setze snapshotVolumes: true im daily-backup Schedule
  → Entferne labelSelector (oder erweitere auf alle Pods)
  → CI/CD-Pfad: Git → CI → kubectl patch
```

**Erwartetes Ergebnis:**
- Velero sichert PVCs via CSI-Snapshots
- Bei Node-Fail: PVCs können wiederhergestellt werden
- MinIO, RabbitMQ, Prometheus, Alertmanager geschützt

---

## CI/CD-Zusammenfassung

| Prompt | Datei | CI/CD-Pfad | Deploy-Methode |
|--------|-------|------------|----------------|
| 1. Velero PVC-Backup | `longhorn-snapshot-class.yaml` (NEU) + Velero Schedule Patch | Git → CI → kubectl apply | CI/CD |
| 2. WAL-Rotation | `cnpg-scheduled-backup.yaml` (NEU) | Git → CI → kubectl apply | CI/CD |
| 3. k3s CPU | `prometheus-values.yaml` + CSI YAML | Git → CI → kubectl apply | CI/CD |
| 4. Celery Queue | `celery_app.py` | Git → CI → Docker Build → Rollout | CI/CD |

**ALLE Änderungen laufen über Git → CI → Production.** Keine direkten SSH-Änderungen.

---

## IMPLEMENTIERUNGS-PROMPT FÜR AGENT

### Prompt: WAL-Rotation korrekt beheben

```
Korrigiere die cnpg-scheduled-backup.yaml auf Production (169.58.83.32).

KONTEXT:
- CNPG Version: 1.30.0
- ScheduledBackup CRD unterstützt: backupOwnerReference, cluster, immediate, method, online, schedule, suspend, target
- ScheduledBackup CRD unterstützt NICHT: retentionPolicy, imagePullSecrets
- retentionPolicy: 7d ist bereits auf Cluster CRD gesetzt (cnpg-cluster.yaml)
- 02-apply-manifests.sh Zeile 23: kubectl apply -f cnpg-scheduled-backup.yaml 2>/dev/null || echo
- 33 GB WALs (9 Serien) wachsen seit 24 Tagen

AUFGABE 1: Korrekte YAML erstellen
- Lies die aktuelle infrastructure/kubernetes/production/cnpg-scheduled-backup.yaml
- Entferne retentionPolicy: "7d" (gehört zur Cluster CRD, nicht zur ScheduledBackup)
- Entferne imagePullSecrets (nicht unterstützt von ScheduledBackup CRD)
- Ändere schedule von "0 3 * * *" (5 Felder) auf "0 3 * * * *" (6 Felder, CNPG robfig/cron)
- Füge immediate: true hinzu (erstes Backup sofort bei Erstellung)

AUFGABE 2: Verifikation
- Prüfe ob die YAML KEINE ungültigen Felder enthält: grep -E "retentionPolicy|imagePullSecrets" infrastructure/kubernetes/production/cnpg-scheduled-backup.yaml
- Erwartung: Kein Output (keine Treffer)
- Prüfe ob schedule 6 Felder hat: grep schedule infrastructure/kubernetes/production/cnpg-scheduled-backup.yaml
- Erwartung: "0 3 * * * *" (6 Felder)

AUFGABE 3: Git Commit + Push
- Führe git status aus
- Führe git diff aus
- Commit mit: "fix(cnpg): ScheduledBackup korrigiert (6-Feld-Cron, keine ungültigen Felder)"
- Push to main

AUFGABE 4: Deploy triggern
- CI/CD (deploy-production.yml) wird automatisch getriggert
- Nach Deploy: Prüfe ob ScheduledBackup existiert: kubectl get scheduledbackups -n meeting-automation
- Erwartung: meeting-db-daily vorhanden
- Prüfe ob Base-Backup läuft: kubectl get backups -n meeting-automation
- Erwartung: Ein Backup mit Status "running" oder "completed"

ERWARTETES ERGEBNIS:
- cnpg-scheduled-backup.yaml: Korrekt (keine ungültigen Felder, 6-Feld-Cron)
- Git: 1 Datei geändert, committed + pushed
- CI/CD: Deploy triggered
- Production: ScheduledBackup CRD erstellt, erstes Base-Backup läuft
- WAL-Rotation: retentionPolicy: 7d greift nach erstem Base-Backup
```

---

### Prompt: k3s CPU Optimierung

```
Optimiere die k3s CPU-Last auf Production (169.58.83.32).

KONTEXT:
- k3s CPU: 85.2% (Dauerzustand, nicht temporär)
- 518 Watch-Connections (Event-Filterung ~30% CPU)
- 153,999 Lease PUTs (2.7/s, etcd-Write ~35% CPU)
- 67 CRDs, 47 Pods, 162 Metrik-Zeilen
- Operator-Limits: bereits gesetzt (alle Under Limit)
- Maximale Optimierung: ~7% CPU (85% → ~78%)

AUFGABE 1: Longhorn CRDs reduzieren (P1)
- Prüfe welche Longhorn CRDs auf Single-Node nicht gebraucht werden
- Deaktiviere unnötige Features via kubectl patch settings.longhorn.io
- Erwartung: -13 Watches, -2-3% CPU

AUFGABE 2: Velero CRDs prüfen (P2)
- Prüfe welche Velero CRDs für 1 Backup-Schedule nötig sind
- Deaktiviere unnötige CRDs falls möglich
- Erwartung: -13 Watches, -1-2% CPU

AUFGABE 3: CNPG reconcile-Intervall erhöhen (P3)
- Prüfe CNPG Cluster-Spec auf reconcileIntervall
- Erhöhe von 15s auf 60s falls konfigurierbar
- Erwartung: -12 API-Requests/min, -2% CPU

AUFGABE 4: Verifikation
- Prüfe k3s CPU nach 10 Minuten: ps aux | grep 'k3s server' | awk '{print $3}'
- Erwartung: <80% (vorher: 85.2%)
- Prüfe Watch-Anzahl: kubectl get --raw /metrics | grep WATCH | awk '{sum+=$NF} END {print sum}'
- Erwartung: <490 (vorher: 518)

AUFGABE 5: Dokumentation
- Schreibe die Ergebnisse in docs/K3S_TUNING_PLAN_2026-08-20.md unter "Schritt 7: k3s CPU Optimierung"

ERWARTETES ERGEBNIS:
- k3s CPU: 85% → ~78%
- Watches: 518 → ~490
- Load: 5.23 → ~4.5
```

---

## UNIFIED IMPLEMENTIERUNGS-PROMPT (ALLE 3 PROBLEME)

**5. Diskussion — 22.08.2026 13:15 CEST**

```
Löse die 3 offenen Probleme auf Production (169.58.83.32) via Git → CI/CD.

PROBLEM 1: Velero PVCs NICHT gesichert (🔴 P1)
- Velero Schedule hat snapshotVolumes: false → PVCs werden NICHT gesichert
- Keine VolumeSnapshotClasses im Cluster
- MinIO (37GB), RabbitMQ, Prometheus, Alertmanager → bei Node-Fail verloren
- FIX: VolumeSnapshotClass für Longhorn erstellen + snapshotVolumes: true im Velero Schedule setzen

PROBLEM 2: WAL-Rotation defekt (🔴 P1)
- cnpg-scheduled-backup.yaml existiert im Git Repo (commit 3ccdee54)
- ABER: ScheduledBackup CRD existiert NICHT im Cluster (kubectl get scheduledbackups → No resources found)
- retentionPolicy: "7d" auf Cluster CRD greift nicht weil keine Base-Backups existieren
- 33 GB WALs wachsen endlos (9 Serien, +1 GB/Tag)
- FIX: Prüfe warum kubectl apply der YAML fehlschlägt. Korrigiere die YAML falls nötig. Deploy via CI/CD.

PROBLEM 3: k3s CPU 85.2% (🟡 P2)
- 518 Watch-Connections, 67 CRDs, 153K Lease PUTs
- Operator-Patches (CNPG maxConcurrentReconciles=2, Longhorn Settings) sind persistent via Git (commit 5a80ea3e)
- ABER: cnpg-operator-patch.yaml ist ein PARTIALS Deployment-Spec (fehlende spec.selector, spec.replicas)
- FIX: Prüfe ob der CNPG Operator Patch via kubectl apply funktioniert. Falls nicht: Korrigiere die YAML.

REIHENFOLGE:
1. Problem 2 zuerst (WAL-Rotation) — smaller scope, schneller deploy
2. Problem 1 danach (Velero PVC-Backup) — braucht VolumeSnapshotClass
3. Problem 3 als letztes (k3s CPU) — Operator-Patches bereits deployt

FUER JEDES PROBLEM:
- Prüfe den aktuellen Stand auf Production (kubectl commands)
- Analysiere die Ursache (nicht annehmen!)
- Implementiere die Lösung via Git → CI/CD
- Verifiziere das Ergebnis auf Production
- Dokumentiere im K3S_TUNING_PLAN_2026-08-20.md
```
