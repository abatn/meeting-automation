# Plan B — Velero Staging reinstallieren (CI-E2E grün)

**Datum:** 2026-09-23  
**Cluster:** OCI Staging (`~/.kube/config-staging`, ARM64, NS `meeting-automation-staging`)  
**Auslöser:** E2E Run `35880016983` (Commit `ba0b3168`) — `deploy-staging-and-test` fail nach ~50s  
**Ursache:** Cleanup 2026-09-23 (`3 uninstall`) hat Velero entfernt (NS + Helm + 13 CRDs); CI macht weiter  
`kubectl apply -f .../velero-backup-repository.yaml` → `no matches for kind BackupRepository`  
**Entscheidung:** Option **B (sauber)** — Velero wieder installieren, CI-Apply bleibt unverändert  

### Dummy (3 Zeilen)

1. **Velero** = Tool, das automatisch Backups vom Staging-Cluster macht.  
2. Wir haben es am Vormittag **absichtlich gelöscht** (Platz sparen) — CI will es aber noch **anschalten** und stürzt deshalb ab.  
3. **Plan B** = sauber wieder installieren, dann läuft der Check wieder grün.

---

## Betroffener Check (nur diese)

| Check | Status (ba0b3168) |
|--------|-------------------|
| Backend CI | ✅ |
| Deploy Staging (Fast) | ✅ (106m) |
| **E2E deploy-staging-and-test** | ❌ **Velero-Apply** |
| E2E build-and-test-dev | ✅ |
| E2E deploy-production | ⏭️ skipped (richtig) |

**Fehler:**
```text
error: ... velero-backup-repository.yaml: no matches for kind "BackupRepository" in version "velero.io/v1"
ensure CRDs are installed first
```

**Ist-Cluster (vor Fix):** kein NS `velero`, keine CRDs, kein Helm-Release; MinIO-Bucket `velero-backups` intakt.

---

## Quellen (Git-History)

| Quelle | Inhalt |
|--------|--------|
| `docs/CLUSTER_CLEANUP_AND_ROLLBACK_PLAN_2026-09-23.md` §5.3 | Uninstall-Log + **Rollback** |
| `/home/opc/cluster-backup-20260923-1227/` | Snapshot Values/Manifest/Secret |
| `infrastructure/kubernetes/staging/velero-values.yaml` | **Aktuelle** Values (Strategie §4) |
| `docs/VELERO_BACKUP_PLAN.md` Phasen 2–5 | Helm-Install, NetPol, Schedule, Smoke |
| Commit `7aac3ebd` | minio-policy velero-NS + Self-Ref Annotation (beides **fehlt** in Git/Live) |
| `docs/AGENT_HANDOFF_2026-08-15.md` | Recovery: Repo-CR auto via erstem Backup |

**Nicht nehmen:** Snapshot-Values (stale: TTL 72h, falscher LabelSelector minio/postgres).

---

## Ausführung

### 1. Helm install (Repo-Values; serviceMonitor aus — Monitoring/CRDs weg)

```bash
export KUBECONFIG=~/.kube/config-staging
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts && helm repo update

helm upgrade --install velero vmware-tanzu/velero \
  -n velero --create-namespace \
  --version 12.1.0 \
  -f infrastructure/kubernetes/staging/velero-values.yaml \
  --set metrics.serviceMonitor.enabled=false \
  --wait
```

### 2. NetworkPolicy minio-policy (ohne das bleibt BSL Unavailable)

```bash
kubectl patch networkpolicy minio-policy -n meeting-automation-staging --type=json \
  -p '[{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"velero"}}}}]'
```

### 3. Self-Ref MinIO (F2 Incident 2026-08-15)

```bash
kubectl annotate sts minio-staging -n meeting-automation-staging \
  backup.velero.io/backup-volumes-excludes="minio-data" --overwrite
```

### 4. CRDs + BackupRepository (CI-Apply-Fallback)

```bash
kubectl get crd | grep velero
kubectl apply -f infrastructure/kubernetes/staging/velero-backup-repository.yaml -n velero
# Primär: Velero legt Repo-CR beim ersten Backup auto an
```

### 5. Smoke

```bash
kubectl get deploy,ds -n velero
# BSL Available + erstes Backup COMPLETED + Repo-CR Ready
velero backup get
kubectl get backuprepositories.velero.io -n velero
```

### 6. Optional Repo-Drift (nach Verify)

- velero-NS-Regel → `network-policies.yaml`
- Annotation → `minio-statefulset.yaml`

---

## Rollback

```bash
export KUBECONFIG=~/.kube/config-staging
helm uninstall velero -n velero
# MinIO-Bucket bleibt; App unberührt; E2E-Apply scheitert wieder wie vorher
```

Snapshot-Fallback (falls Values-Upgrade schlägt):
```bash
helm install velero velero/velero -n velero --create-namespace \
  --version 12.1.0 \
  -f /home/opc/cluster-backup-20260923-1227/velero-values.yaml
kubectl apply -f /home/opc/cluster-backup-20260923-1227/velero-s3-credentials.yaml
```

---

## Verify-Checkliste

- [x] Helm Release `velero` → `deployed` (rev 2)
- [x] CRDs `backuprepositories.velero.io` etc. vorhanden
- [x] Deploy + node-agent Running
- [x] BSL `default` Available
- [x] minio-policy enthält namespace `velero`
- [x] minio-staging Annotation gesetzt
- [x] Smoke-Backup COMPLETED (scoped)
- [x] Repo-CR `meeting-automation-staging-default-kopia` Ready
- [x] E2E `Deploy All Staging Resources` **success** (Retry 35880016983)
- [x] E2E Job `deploy-staging-and-test` **conclusion=success** (Steps: Backend/Frontend/Celery Deploy + Port-forward/E2E + Pass-Rate-Gate)
- [x] `build-and-test-dev` **success**; `deploy-production` **waiting** (nicht freigeben)

## Risiko

| Punkt | Detail |
|--------|--------|
| Disk | ~80% belegt, ~37G frei — Scope n8n+sentinel, kein MinIO/PG |
| Monitoring | serviceMonitor aus; bei Monitoring-Restack wieder an |
| Production | **nicht** anfassen, kein `deploy-production` |
| Löschen | tabu (AGENTS: Ursache beheben, nicht Monitor löschen) |

## Status (Ausführung 2026-09-23 18:07–18:12 UTC)

| Schritt | Status |
|---------|--------|
| MD notiert | ✅ |
| 1 Helm install (Repo-Values, serviceMonitor aus) | ✅ rev 1 |
| 1b `deployNodeAgent=true` (FSB; fehlte in Repo-Values) | ✅ rev 2 |
| 2 minio-policy velero-NS (1×, deduped) | ✅ |
| 3 Self-Ref Annotation minio-staging | ✅ |
| 4 BackupRepository apply (CI-Pfad) | ✅ **EXIT:0** |
| 5 Smoke (scoped n8n+sentinel) | ✅ **Completed** (`plan-b-smoke2-*`, PVB kopia ~1.1G) |
| Verify | Helm deployed · BSL Available · Repo-CR Ready · node-agent 1/1 · schedule Enabled |
| E2E Retry | **Velero-Step grün** seit Retry; `Deploy All Staging Resources` success |
| E2E Run 35880016983 | `deploy-staging-and-test` **success** · `build-and-test-dev` **success** · `deploy-production` **waiting** (manuelld) |
| 6 Repo-Drift | ✅ `deployNodeAgent` in values · ✅ NetPol velero-NS in `network-policies.yaml` · ✅ Self-Ref Annotation in `minio-statefulset.yaml` (CI-Apply entfernte Live-Patches → in Git festgehalten) |

### Befunde bei Ausführung

- Erster Smoke (ohne node-agent): **PartiallyFailed** — `daemonset pod not found` (FSB).
- Fix: `--set deployNodeAgent=true` → Helm rev 2, DS Running.
- Zweiter Smoke (scoped): **Completed**, 0 Errors, PVBs Completed.
- Host-`velero describe/logs` DNS-Fehler gegen `*.svc` = nur CLI außerhalb Cluster (nicht Cluster-Bug).
- CI-kritischer Apply: `kubectl apply -f .../velero-backup-repository.yaml -n velero` → **EXIT:0**.
- **CI-Drift:** `e2e-tests.yml` applies `network-policies.yaml` + `minio-statefulset.yaml` und strich Live-Patches (velero-NS-Regel, Annotation) — deshalb beides **im Git** statt nur live.
