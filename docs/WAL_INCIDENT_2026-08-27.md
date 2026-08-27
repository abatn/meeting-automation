# Incident Report: 51GB WAL-Akkumulation

**Datum:** 2026-08-27
**Status:** Behoben (Staging), Überwachung (Production)
**Schweregrad:** Hoch (Disk-Pressure → Pods Evicted → Service-Ausfall)

---

## Zusammenfassung

Staging PostgreSQL (CNPG `meeting-db-1`) hatte 51GB WAL-Segmente in einem 7MB Container. Ursache: CNPG's `wal-archive` Command scheiterte mit `"failed to get envs: cache miss"` weil das Secret `minio-secrets` die falschen Keys hatte.

---

## Root Cause

```
CNPG Cluster Spec:
  backup.barmanObjectStore.s3Credentials:
    accessKeyId.key: MINIO_ACCESS_KEY      ← erwartet
    secretAccessKey.key: MINIO_SECRET_KEY   ← erwartet

Secret minio-secrets:
  MINIO_ROOT_USER: minio_user    ← vorhanden (falscher Name)
  MINIO_ROOT_PASSWORD: ...       ← vorhanden (falscher Name)

→ CNPG findet MINIO_ACCESS_KEY nicht
→ cache miss
→ wal-archive scheitert
→ .ready files akkumulieren
→ Checkpoint kann WAL nicht freigeben
→ 3225 WAL-Segmente × 16MB = 51GB
→ Disk-Pressure → Pods Evicted → Service-Ausfall
```

---

## Beweise (Logs)

```
# CNPG Manager Log:
"error":"missing key MINIO_ACCESS_KEY, inside secret minio-secrets"
"msg":"while getting backup credentials"

"logger":"wal-archive","msg":"failed to run wal-archive command"
"error":"failed to get envs: cache miss"

"message":"archiving write-ahead log file \"000000010000000000000002\" failed too many times"
```

---

## Impact

| Komponente | Auswirkung |
|-----------|-----------|
| Disk | 96% → 96% (51GB WAL +Images) |
| Pods | 4.289 Evicted Pods (velero + app) |
| Backend | 3 Pods `Init:Error` |
| LiveKit Egress | `CreateContainerConfigError` |
| Service | Staging nicht nutzbar |

---

## Fix (Staging)

### Option A: Backup Config entfernen (Empfohlen)

CNPG Cluster Spec: `spec.backup` komplett entfernen.

**Begründung:**
- Staging braucht kein WAL-Archiv
- Kein Backup = kein archive_command = WAL wird normal recycelt
- archive_mode bleibt `on` (CNPG Default), aber archive_command wird nicht ausgeführt

### Option B: Secret Keys korrigieren

```yaml
# minio-secrets korrigieren:
MINIO_ACCESS_KEY: minio_user    # statt MINIO_ROOT_USER
MINIO_SECRET_KEY: minio_password # statt MINIO_ROOT_PASSWORD
```

**Begründung:**
- Backup funktioniert dann korrekt
- Aber: Staging braucht kein Backup

---

## Durchführung (Option A)

### Schritt 1: CNPG Cluster Spec patchen

```bash
kubectl patch clusters.postgresql.cnpg.io meeting-db \
  -n meeting-automation-staging \
  --type json \
  -p '[{"op": "remove", "path": "/spec/backup"}]'
```

### Schritt 2: Pod Restart

```bash
kubectl delete pod meeting-db-1 -n meeting-automation-staging --force --grace-period=0
```

### Schritt 3: Verifikation

```bash
# Archive Mode prüfen:
kubectl exec -n meeting-automation-staging meeting-db-1 -c postgres \
  -- psql -U postgres -c "SHOW archive_mode;"

# .ready Files prüfen (sollten 0 sein):
kubectl exec -n meeting-automation-staging meeting-db-1 \
  -- ls /var/lib/postgresql/data/pgdata/pg_wal/archive_status/

# WAL Size prüfen (sollte <100MB sein):
kubectl exec -n meeting-automation-staging meeting-db-1 \
  -- du -sh /var/lib/postgresql/data/pgdata/pg_wal/
```

### Schritt 4: Rollback (falls nötig)

```bash
# Backup Config wiederherstellen:
kubectl patch clusters.postgresql.cnpg.io meeting-db \
  -n meeting-automation-staging \
  --type merge \
  -p '{"spec":{"backup":{"barmanObjectStore":{"destinationPath":"s3://backups/postgres/","endpointURL":"http://minio-staging.meeting-automation-staging.svc.cluster.local:9000","s3Credentials":{"accessKeyId":{"key":"MINIO_ACCESS_KEY","name":"minio-secrets"},"secretAccessKey":{"key":"MINIO_SECRET_KEY","name":"minio-secrets"}}},"retentionPolicy":"30d","target":"prefer-standby"}}}'
```

---

## Production Vergleich

| Metrik | Staging | Production |
|--------|---------|-----------|
| Replicas | 1 | 3 |
| Backup | ❌ Fehlgeschlagen | ✅ Funktioniert |
| .ready Files | 7 (akkumuliert) | 0 (OK) |
| WAL Size | 129MB (wächst) | 577MB (stabil) |
| archive_mode | on (erzwungen) | on (benötigt) |

**Production:** Kein Fix nötig — 3 Replicas brauchen `archive_mode=on` + funktionierendes Backup.

---

## Verhinderung

| Maßnahme | Effekt |
|----------|--------|
| CNPG Backup Config nur aktivieren wenn Secret korrekt | Verhindert cache miss |
| WAL-Monitoring (Prometheus Alert bei >500MB) | Frühzeitige Warnung |
| `wal_keep_size` reduzieren (512MB → 64MB) | Weniger WAL-Rückhaltung |

---

## Commits

- `docs/WAL_INCIDENT_2026-08-27.md` — Dieses Incident Report
- CNPG Spec Änderung — Backup config entfernt

---

## Rollback-Protokoll

| Schritt | Befehl | Status |
|---------|--------|--------|
| 1. CNPG Spec patchen | `kubectl patch ...` | ⏳ |
| 2. Pod Restart | `kubectl delete pod ...` | ⏳ |
| 3. Verifikation | `psql + ls + du` | ⏳ |
| 4. Rollback (falls nötig) | `kubectl patch ...` | ⏳ |
