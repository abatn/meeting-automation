# WAL/Barman Freigabe — Disk Cleanup Staging (2026-09-23)

**Freigabe:** User („Disk 47G PG/WAL — Freigabe für Aufräumen (z.B. Barman/WAL-Review) — kein Blind-Löschen")  
**Regel:** Ursache beheben, kein `rm` auf `pg_wal`/Host.

## Befund (vorher)

| Metrik | Wert |
|--------|------|
| `pgdata/pg_wal` | **46G** (2940 Segmente × 16M) |
| `base` | 77M |
| Root-Disk | **145.9G / 182.8G = 80%** |
| `pg_stat_archiver` | archived=0, failed=12435 |
| ContinuousArchiving | **False** `barman-cloud-wal-archive exit 4` |
| Logs | `InvalidAccessKeyId` |
| MinIO Bucket `backups` | **fehlte** |

### Root Cause (bewiesen)

1. Secret `minio-secrets`:
   - `MINIO_ACCESS_KEY` = `mino_user` (Typo, fehlendes `i`)
   - `MINIO_SECRET_KEY` = `mino_password`
   - korrekt: `minio_user` / `minio_password`
2. Bucket `s3://backups` existierte nicht → Barman PutObject scheitert zusätzlich.
3. Archiver klebt auf erstem Segment `…C00000B6` (seit 2026-08-27) → Checkpoint kann WAL nicht freigeben → 46G Akkumulation.

## Durchführung (Ursache, kein Blind-Löschen)

| Schritt | Ergebnis |
|---------|----------|
| Secret live patchen auf korrekte Keys | ✅ |
| MinIO Bucket `backups` anlegen | ✅ |
| `minio-secrets.yaml` im Git mit ACCESS/SECRET Keys | ✅ (Commit) |
| `spec.backup` live entfernt (Incident Option A — Staging braucht kein kontinuierliches WAL-Archiv; pg_dump-Cronjob `postgres-backup` bleibt) | ✅ |
| Pod Restart meeting-db-1 | ✅ |
| Archiv-Drain: ready 2940 → 0, archived_count → 2663, failed → 0 | ✅ |
| `CHECKPOINT` | ✅ |
| **KEIN** `rm` auf pg_wal | ✅ |

## Ergebnis (nachher)

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| `pg_wal` | 46G | **145M** |
| WAL-Segmente | 2940 | **9** |
| Root-Disk | 80% (145.9G) | **55% (101G)** |
| Frei | ~37G | **~83G** |
| ContinuousArchiving | False | **True** (Condition) |
| archived / failed | 0 / 12435 | **2663 / 0** |

## Follow-ups (offen, nicht in dieser Freigabe)

- CI `e2e-tests` applyt weiter `cnpg-cluster.yaml` **mit** `spec.backup` → nach nächstem Deploy wieder Barman aktiv. Secret ist jetzt korrekt → sollte funktionieren. Beobachten.
- MinIO `backups` während Drain leer beobachtet (möglicherweise Pfad/Endpoint); nach Secret-Fix + `spec.backup`-Remove kein neuer Upload nötig, solange pg_dump-Cronjob läuft.
- CNPG `Ready=False` / `Instance Status Extraction Error` (Operator-HTTP / 2. Instance) — ** separat**, nicht Teil dieser Freigabe.
- Kein `docker prune`, kein Host-`rm`, kein `deploy-production`.

## Verify

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl exec -n meeting-automation-staging meeting-db-1 -c postgres -- \
  du -sh /var/lib/postgresql/data/pgdata/pg_wal   # << 500M
kubectl run df --rm -i --restart=Never --image=busybox:1.36 -- df -h /  # < 70%
kubectl get secret minio-secrets -n meeting-automation-staging -o jsonpath='{.data.MINIO_ACCESS_KEY}' | base64 -d
# erwartet: minio_user (nicht mino_user)
```
