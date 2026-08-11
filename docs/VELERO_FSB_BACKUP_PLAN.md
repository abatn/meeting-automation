# Velero FSB Backup Plan — Wichtige PVCs

**Erstellt:** 2026-08-11
**Status:** Plan (nicht deployt)
**Cluster:** Staging (OCI) + Production (Contabo)

---

## 1. PVC-Ranking nach Wichtigkeit

### P0 — KRITISCH (Datenverlust = Geschäftsende)

| PVC | Größe | Service | Inhalt | Backup-Priorität |
|-----|-------|---------|--------|------------------|
| `postgres-data-postgres-staging-0` | 10Gi | PostgreSQL | Alle Kundendaten, Sessions, Transkripte, Nutzer | **KRITISCH** |
| `minio-data-minio-staging-0` | 10Gi | MinIO | Meeting-Recordings (OGG/WAV), PDFs, Velero-Backups | **KRITISCH** |
| `meeting-db-1` | 10Gi | PostgreSQL (legacy) | Backup/Shadow-DB | **HOCH** |

### P1 — HOCH (Wiederherstellbar, aber aufwendig)

| PVC | Größe | Service | Inhalt | Backup-Priorität |
|-----|-------|---------|--------|------------------|
| `sentinel-models-claim` | 2Gi | Celery Worker | Qwen GGUF-Modell für Speaker-Identification | **HOCH** |
| `rabbitmq-staging-storage-rabbitmq-staging-0` | 5Gi | RabbitMQ | Message-Queue-State, DLQ | **MITTEL** |

### P2 — NIEDRIG (Rekonstruierbar)

| PVC | Größe | Service | Inhalt | Backup-Priorität |
|-----|-------|---------|--------|------------------|
| `n8n-staging-pvc` | 1Gi | n8n | Workflow-Execution-State | **NIEDRIG** |
| `postgres-backup-pvc` | 5Gi | CronJob | Alte DB-Dumps ( redundante Sicherung) | **NIEDRIG** |

---

## 2. Backup-Strategie

### Empfehlung: 2 Separate Backup-Schedules

**Schedule 1: `daily-full-backup`** (Metadaten + kleine PVCs)
- Häufigkeit: Täglich 02:00
- TTL: 168h (7 Tage)
- Umfang: Alle Namespace-Resources + FSB für P1+P2 PVCs
- Geschätzte Größe: ~8-10Gi (Kopia-komprimiert)

**Schedule 2: `weekly-critical-backup`** (Nur kritische PVCs)
- Häufigkeit: Wöchentlich Sonntag 03:00
- TTL: 720h (30 Tage)
- Umfang: Nur P0 PVCs (PostgreSQL + MinIO)
- Geschätzte Größe: ~15-20Gi (Kopia-komprimiert)

### Alternative: Ein Schedule mit Selector

Falls ein Schedule bevorzugt wird:
- `--selector 'app not in (postgres-staging,minio-staging)'` für Metadata-only
- Separate manuelle Backups für kritische PVCs

---

## 3. Implementierung (Velero Annotations)

### Methode: Pod-Annotations für FSB-Steuerung

Mit `configuration.defaultVolumesToFsBackup=true` werden ALLE Pod-Volumes gesichert.
Um dies zu steuern, nutze Annotations:

```yaml
# Auf Pods, die NICHT gesichert werden sollen:
annotations:
  backup.velero.io/backup-volumes-excludes: "data,logs"

# Auf Pods, die gesichert werden sollen (opt-in):
annotations:
  backup.velero.io/backup-volumes: "data"
```

### Empfohlene Annotations pro Pod

| Pod | Annotation | Effekt |
|-----|-----------|--------|
| `postgres-staging-0` | `backup.velero.io/backup-volumes: "data"` | ✅ PostgreSQL sichern |
| `minio-staging-0` | `backup.velero.io/backup-volumes: "data"` | ✅ MinIO sichern |
| `rabbitmq-staging-0` | `backup.velero.io/backup-volumes: "data"` | ✅ RabbitMQ sichern |
| `celery-worker-pro-staging` | `backup.velero.io/backup-volumes: "sentinel-models"` | ✅ Models sichern |
| `n8n-staging` | `backup.velero.io/backup-volumes-excludes: "data"` | ❌ n8n überspringen |
| `backend` | `backup.velero.io/backup-volumes-excludes: "*"` | ❌ Stateless, überspringen |
| `frontend` | `backup.velero.io/backup-volumes-excludes: "*"` | ❌ Stateless, überspringen |

---

## 4. Disk-Anforderungen

| Backup-Typ | Quelle | Kopia-Repo | Geschätzte Größe | Mindest-Freispeicher |
|------------|--------|-----------|-----------------|---------------------|
| Metadaten only | Alle Resources | `default` | ~500K | 1G |
| P1+P2 PVCs (8Gi) | n8n+sentinel+rabbitmq | `default` | ~3-5Gi | 10G |
| P0 PVCs (30Gi) | postgres+minio | `default` | ~15-20Gi | 40G |
| Alle PVCs (38Gi) | komplett | `default` | ~20-25Gi | 50G |

### Staging Disk-Status

```
Aktuell: 63% (69G frei)
Empfohlen für Full Backup: 50G frei → 73% belegt
Status: ✅ AUSREICHEND
```

---

## 5. Befehle

### Step 1: Velero Hub auf korrekten Key prüfen

```bash
helm get values velero -n velero | grep defaultVolumesToFsBackup
# Erwartet: configuration.defaultVolumesToFsBackup: true
```

### Step 2: Pods mit Annotations versehen (optional)

```bash
# PostgreSQL: FSB aktivieren
kubectl annotate pod postgres-staging-0 -n meeting-automation-staging \
  backup.velero.io/backup-volumes=data --overwrite

# MinIO: FSB aktivieren
kubectl annotate pod minio-staging-0 -n meeting-automation-staging \
  backup.velero.io/backup-volumes=data --overwrite

# n8n: FSB deaktivieren
kubectl annotate pod n8n-staging-* -n meeting-automation-staging \
  backup.velero.io/backup-volumes-excludes=data --overwrite
```

### Step 3: Backup-Schedule erstellen

```bash
# Metadaten + kleine PVCs (täglich)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --ttl=168h \
  --include-namespaces=meeting-automation-staging

# Kritische PVCs (wöchentlich)
velero schedule create weekly-critical-backup \
  --schedule="0 3 * * 0" \
  --ttl=720h \
  --include-namespaces=meeting-automation-staging \
  --selector 'app in (postgres-staging,minio-staging)'
```

### Step 4: Erstes Backup manuell testen

```bash
# Metadaten-only (schnell, ~13 Sekunden)
velero backup create test-metadata-only \
  --include-namespaces=meeting-automation-staging \
  --selector 'app in (n8n-staging)' \
  --wait

# Mit kleinem PVC (sentinel-models, 2Gi)
velero backup create test-small-pvc \
  --include-namespaces=meeting-automation-staging \
  --selector 'app=celery-worker-pro-staging' \
  --wait

# Kritische PVCs (postgres + minio, ~30Gi)
velero backup create test-critical-pvc \
  --include-namespaces=meeting-automation-staging \
  --selector 'app in (postgres-staging,minio-staging)' \
  --wait
```

---

## 6. Monitoring

### Wichtige Metriken

| Metrik | Alert-Schwelle |
|--------|----------------|
| `velero_backup_successful` | = 0 nach Schedule |
| `velero_backup_duration_seconds` | > 3600s (1h) |
| `velero_backup_partial_failure_count` | > 0 |

### Täglicher Check

```bash
velero backup get | tail -5
velero schedule get
velero backup-location get
```

---

## 7. Lektionen aus dem FSB-Test (2026-08-11)

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `defaultVolumesToFsBackup` nicht wirksam | Falscher Helm-Key (top-level statt `configuration.`) | `configuration.defaultVolumesToFsBackup=true` |
| Node-Agent Eviction | 55Gi Backup-Daten → Disk-Pressure | Nur kritische PVCs sichern, nicht alle |
| Kopia Repository nicht initialisiert | Gelöschte MinIO-Daten | MinIO velero-backups Bucket leer lassen vor erstem Backup |
| Backup-Größe 764K (keine PVCs) | FSB nicht aktiviert | Helm-Key korrigieren |
| Backup-Größe 57Gi (zu groß) | Alle PVCs inkl. MinIO (10Gi) + PostgreSQL (10Gi) | Selektive Backups mit `--selector` |
