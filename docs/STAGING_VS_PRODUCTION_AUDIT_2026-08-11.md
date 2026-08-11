# Staging vs Production Audit — 2026-08-11

**Status:** AUDIT ABGESCHLOSSEN
**Erstellt:** 2026-08-11
**Cluster:** Staging (OCI 158.180.18.110) + Production (Contabo 169.58.83.32)

---

## Phase 2: Vergleich (Staging vs Production)

### Ist-Zustand Tabelle

| Resource | Staging | Production | Delta | Aktion |
|----------|---------|------------|-------|--------|
| **Disk Usage** | 63% (115G/183G) | 68% (195G/290G) | +5% | ⚠️ Monitoring |
| **PG Version** | 18.3 (ARM64) | 18.4 (AMD64) | Minor | ✅ Keine Aktion |
| **pg_dump Image** | `postgres:15-alpine` | `postgres:15-alpine` | Identisch | 🔴 **KRITISCH: Image ist veraltet** |
| **StorageClass Default** | `local-path` (kein Default) | `local-path` (kein Default) | Identisch | ⚠️ Kein Default-SC |
| **PVC Total** | 43Gi (7 PVCs) | 43Gi (7 PVCs) | Identisch | ✅ OK |
| **Longhorn Volumes** | 0 | 0 | Identisch | ⚠️ Longhorn installiert aber ungenutzt |
| **Velero Backups** | 0 (FSB deaktiviert) | 3 (FSB aktiv) | -3 | ⚠️ Staging ohne FSB |
| **MinIO Size** | 1.1Gi | 32Gi | +30.9Gi | ⚠️ Production hat mehr Daten |
| **Namespace** | `meeting-automation-staging` | `meeting-automation` | — | ✅ OK |
| **Node Arch** | ARM64 (aarch64) | AMD64 (x86_64) | — | ✅ OK |

### Detaillierte Analyse

#### 1. pg_dump Image (KRITISCH)

```
BEIDE Cluster: postgres:15-alpine
PostgreSQL Version: Staging 18.3, Production 18.4
Problem: pg_dump 15 kann kein PG 18 dumpen!
```

**Risiko:** `pg_dump` aus Image `postgres:15-alpine` erzeugt ein Dump im PG 15-Format. Bei einem Restore auf PG 18 kann es zu Kompatibilitätsproblemen kommen. Mindestens muss das Image auf `postgres:18-alpine` aktualisiert werden.

**Empfehlung:** `postgres:18-alpine` (gleiche Major-Version wie die DB)

#### 2. StorageClass

```
BEIDE Cluster: local-path (kein Default-Annotation)
Longhorn: installiert aber 0 Volumes
```

**Problem:** Kein StorageClass als Default markiert. Bei PVCs ohne `storageClassName` wird `local-path` verwendet (k3s Default), aber das ist nicht explizit.

**Empfehlung:** `local-path` als Default markieren (nicht Longhorn — local-path ist performanter für Single-Node)

#### 3. Velero FSB

```
Staging: FSB deaktiviert (configuration.defaultVolumesToFsBackup=false)
Production: FSB aktiv (configuration.defaultVolumesToFsBackup=true)
```

**Grund:** Staging Disk (183G) ist zu klein für Full-FSB-Backups (~40Gi Kopia-Daten + 115Gi bestehende Daten = 155Gi → 85%+ → DiskPressure).

**Empfehlung:** Staging bleibt ohne FSB. Production behält FSB.

#### 4. Ephemeral Storage

```
BEIDE Cluster: Keine ephemeral-storage Limits definiert
```

**Risiko:** Pods können unbegrenzt ephemeral Storage verwenden → DiskPressure.

**Empfehlung:** `ephemeral-storage` Limits für alle Pods hinzufügen.

---

## Phase 3: Fix-Vorschläge

### Fix 1: pg_dump Image (KRITISCH)

**Problem:** `postgres:15-alpine` ist veraltet und inkompatibel mit PG 18.

**Lösung:**
```yaml
# postgres-backup-cronjob.yaml
image: postgres:18-alpine  # war: postgres:15-alpine
```

**Staging-Test:** CronJob manuell ausführen, Output prüfen:
```bash
kubectl create job --from=cronjob/postgres-backup test-backup -n meeting-automation-staging
kubectl logs -f job/test-backup -n meeting-automation-staging
```

**Risiko:** Niedrig — `pg_dump` aus PG 18 Image ist abwärtskompatibel.

### Fix 2: StorageClass Default

**Problem:** Kein expliziter Default-StorageClass.

**Lösung:**
```bash
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

**ACHTUNG:** Bestehende PVCs bleiben bei `local-path` (keine Änderung). Nur NEUE PVCs nutzen den Default.

**Risiko:** Niedrig — nur Änderung der Annotation.

### Fix 3: Ephemeral Storage Limits

**Problem:** Keine Limits → Pod kann Disk füllen.

**Lösung:**
```yaml
resources:
  limits:
    ephemeral-storage: 2Gi
  requests:
    ephemeral-storage: 200Mi
```

**Risiko:** Niedrig — nur Limits hinzugefügt.

### Fix 4: Disk Cleanup (sicher)

**Lösung:**
```bash
journalctl --vacuum-size=100M
find /var/log/pods -name "*.log" -mtime +2 -delete
```

**VERBOTEN:** `docker system prune`, `k3s ctr images prune --all`

**Risiko:** Keins — nur Logs aufräumen.

---

## Phase 4: Production Plan (nach GO)

### Schritt 1: Backup VOR Änderungen

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Velero Backup
velero backup create pre-fix-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation \
  --wait
```

### Schritt 2: pg_dump Image updaten

```bash
# CronJob Image ändern
kubectl set image cronjob/postgres-backup pg-dump=postgres:18-alpine \
  -n meeting-automation

# Verifikation
kubectl get cronjob postgres-backup -n meeting-automation \
  -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].image}'
```

### Schritt 3: StorageClass Default setzen

```bash
kubectl patch storageclass local-path -p \
  '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### Schritt 4: Ephemeral Storage Limits

```yaml
# Für ALLE Deployments/StatefulSets in meeting-automation:
resources:
  limits:
    ephemeral-storage: 2Gi
  requests:
    ephemeral-storage: 200Mi
```

### Schritt 5: Disk Cleanup

```bash
journalctl --vacuum-size=100M
find /var/log/pods -name "*.log" -mtime +2 -delete
```

### Schritt 6: Verifikation

```bash
# PG Backup Test
kubectl create job --from=cronjob/postgres-backup test-backup -n meeting-automation
kubectl logs -f job/test-backup -n meeting-automation

# Disk Check
df -h /

# Velero Backup nach Fix
velero backup create post-fix-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation \
  --wait
```

---

## Rückroll-Plan

### Fix 1 (pg_dump Image):
```bash
kubectl set image cronjob/postgres-backup pg-dump=postgres:15-alpine \
  -n meeting-automation
```

### Fix 2 (StorageClass):
```bash
kubectl patch storageclass local-path -p \
  '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

### Fix 3 (Ephemeral Storage):
Limits aus den Deployment/StatefulSet YAMLs entfernen.

### Fix 4 (Disk Cleanup):
Kein Rückroll nötig (Logs werden automatisch neu geschrieben).

---

## Zusammenfassung

| Fix | Priorität | Risiko | Aufwand | Staging getestet? |
|-----|-----------|--------|---------|-------------------|
| pg_dump Image | 🔴 KRITISCH | Niedrig | 5 Min | ❌ Nein |
| StorageClass Default | 🟡 MITTEL | Niedrig | 2 Min | ❌ Nein |
| Ephemeral Storage | 🟡 MITTEL | Niedrig | 15 Min | ❌ Nein |
| Disk Cleanup | 🟢 NIEDRIG | Keins | 2 Min | ❌ Nein |

**Empfehlung:** Fix 1 (pg_dump) SOFORT auf Staging testen, dann Production. Fix 2-4 können parallel getestet werden.
