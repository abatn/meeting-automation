# Agent-Handoff — 6 Prompts nach Staging-Recovery (2026-08-15)

**Kontext:** Staging-Cluster (OCI 158.180.18.110) hat einen Velero-Ausfall ueberlebt. Disk ist jetzt 73%
(50G frei). Velero ist gestoppt. App-Deployments laufen. 6 offene Punkte bleiben.

**Wichtigste Dateien:**
- `docs/INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` — vollstaendiger Incident-Report mit Phasen 1-5
- `docs/INCIDENT_REPORT_STAGING_2026-08-15.md` — vorheriger Report (Phase 0-3 Fixes, teils erledigt)
- `docs/VELERO_BACKUP_PLAN.md` — Velero-Doku
- `docs/AUTOSCALING_ARCHITECTURE_2026-08-14.md` — KEDA/HPA-Doku

**SSH-Zugang:** Direkt auf 158.180.18.110 (kein SSH noetig, wir sind dort).
**Kubectl:** `export KUBECONFIG=/etc/rancher/k3s/k3s.yaml` + `sudo /usr/local/bin/k3s kubectl`

---

## Prompt 1: Velero permanent wiederherstellen (F1-F4)

Du bist Velero-Recovery-Agent. Velero ist auf Staging seit 4h gestoppt (Deployment 0/0, Node-Agent geloescht).
Deine Aufgaben:

1. **Velero Deployment neu starten** (replicas=1), ABER nur wenn:
   - Der `velero-backups` Bucket in MinIO existiert (er wurde geleert + neu erstellt via `mc mb`)
   - Der `daily-backup` Schedule noch Enabled ist
   
2. **Node-Agent DaemonSet wiederherstellen** (loesche den alten DS, falls noetig, und laess den Helm-Chart/Manifest-Apply einen neuen erstellen)

3. **Fehlende BackupRepository CRD wiederherstellen** — wenn die CRD `meeting-automation-staging-default-kopia` geloescht wurde, muss Velero sie beim naechsten Backup neu initialisieren. Teste das mit einem manuellen Backup:
   ```
   velero backup create recovery-test-$(date +%s) --include-namespaces meeting-automation-staging --wait
   ```

4. **Velero-Selbstreferenz verhindern** — waehrend Velero noch NICHT die MinIO-PVC sichert, setze die Annotation am minio-StatefulSet:
   ```yaml
   backup.velero.io/backup-volumes-excludes: "minio-data"
   ```
   Quelle: https://velero.io/docs/main/file-system-backup/ (opt-out approach)

5. **Scope korrigieren** — der `daily-backup` Schedule hat `labelSelector: app In [minio-staging, postgres-staging]`. Das ist RESTRIKTIV und sichert minio (Selbst-Referenz) aber NICHT n8n. Korrigiere den Selector oder entferne ihn (je nach Bedarf).

6. **Verifikation:** `velero schedule get`, `velero backup get`, `df -h /` (Disk darf nicht wieder steigen)

**Dateien:** `docs/VELERO_BACKUP_PLAN.md` (aktualisieren), `docs/INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` (Status aktualisieren)

---

## Prompt 2: CNPG NetworkPolicy beheben

Du bist CNPG-NetworkPolicy-Agent. Das Problem: CNPG-Operator (namespace `cnpg-system`) kann die meeting-db Instanz (namespace `meeting-automation-staging`) nicht erreichen.

**Beweis:**
```
Get "https://10.42.0.208:8000/pg/status": dial tcp 10.42.0.208:8000: connect: no route to host
```

**Deine Aufgaben:**

1. **NetworkPolicies analysieren** — pruefe ALLE NetworkPolicies in beiden Namespaces:
   ```
   kubectl get networkpolicy -n meeting-automation-staging -o yaml
   kubectl get networkpolicy -n cnpg-system -o yaml
   ```

2. **Root-Cause finden** — gibt es eine `default-deny-all` Policy die den Cross-Namespace-Traffic blockiert?

3. **Korrigierte Policy formulieren** — erstelle eine Erlaubnis-Regel die `cnpg-system` erlaubt, auf Port 8000 in `meeting-automation-staging` zuzugreifen. Nur analysieren + vorschlagen, nicht ausfuehren.

4. **AUCH pruefen:** Warum gibt es `meeting-db-2` und `meeting-db-3` NICHT? Der Cluster-Spec sagt `instances: 1`. Ist das beabsichtigt?

**Dateien:** `docs/INCIDENT_REPORT_STAGING_2026-08-15.md` (NetworkPolicy-Fund dokumentieren)

---

## Prompt 3: Evicted-Pods aufraeumen + Garbage-Collector verifizieren

Du bist Cleanup-Agent. Auf Staging gibt es noch **5342 Evicted-Pods** (die meisten im velero-Namespace). Der pod-garbage-collector CronJob laeuft (alle 15min), aber er loescht velero- evicted Pods NICHT (da velero-Deployment 0/0 ist und die Pods orphaned sind).

**Deine Aufgaben:**

1. **Evicted-Pod-Analyse** — zaehle nach Namespace:
   ```
   kubectl get pods -A --no-headers | awk '$4=="Evicted"{print $1}' | sort | uniq -c
   ```

2. **Velero-Evicted-Pods manuell loeschen** — diese werden vom GC nicht aufgeraeumt weil der RS 0 desired hat und orphaned Pods nicht im GC-Scope sind:
   ```
   kubectl delete pods -n velero --field-selector=status.phase=Failed --ignore-not-found
   ```
   Hinweis: 5000+ Pods — kann dauern. Alternativ: `kubectl delete pod -n velero -l app.kubernetes.io/name=velero --field-selector=status.phase=Failed` (falls Label vorhanden).

3. **Pod-GC CronJob pruefen** — hat er die korrekte ClusterRole mit `pods:get` (aus dem frueheren Fix)?
   ```
   kubectl get clusterrole pod-gc -o yaml | grep -A3 "apiGroups"
   ```

4. **Verifikation:** Nach dem Cleanup sollte `kubectl get pods -A --field-selector=status.phase=Failed -o name | wc -l` nahe 0 sein.

**Dateien:** `docs/INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` (evicted count aktualisieren)

---

## Prompt 4: Ephemeral-Storage-Alerts + kubelet-Reservierung (F5-F6)

Du bist Monitoring-Agent. Die Disk ist bei 73%, aber es gibt keinen Alert der bei ephemeral-storage-Druck warnt.

**Deine Aufgaben:**

1. **Prometheus-Rules pruefen** — lese `infrastructure/kubernetes/staging/monitoring/prometheus-rules.yaml` und pruefe ob ein `EphemeralStorageHigh` Alert existiert (PVC-Alerts wurden frueher hinzugefuegt, aber kein ephemeral-storage).

2. **Fehlenden Alert formulieren** — erarbeite eine Prometheus-Alert-Regel fuer:
   - `kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes < 0.2` (PVC >80% voll)
   - Node-level ephemeral-storage: waere ideal `node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.2`

3. **kubelet-Reservierung (F6) pruefen** — in `/etc/rancher/k3s/config.yaml` gibt es `kubelet-arg: image-gc-*`. Pruefe ob `system-reserved` oder `eviction-hard` gesetzt sind. Formuliere die korrekte Reservierung:
   ```
   kubelet-arg:
     - "system-reserved=cpu=500m,memory=1Gi,ephemeral-storage=5Gi"
     - "eviction-hard=nodefs.available<10%"
   ```

4. **Datei aendern (Git, nicht live):** Nur die YAML-Datei in Git aendern, NICHT live auf dem Cluster (benoetigt k3s-Neustart).

**Dateien:** `infrastructure/kubernetes/staging/monitoring/prometheus-rules.yaml`, `/etc/rancher/k3s/config.yaml` (Doku in Git)

---

## Prompt 5: CI/CD Git-Sync (Commit + Push)

Du bist CI/CD-Agent. Alle manuellen Aenderungen muessen in Git committed werden.

**Befehle:**
```bash
cd /home/opc/meeting-automation
git status --short
git diff
git log --oneline -5
```

**Deine Aufgaben:**

1. **Alle geaenderten Dateien sammeln** (`git status --short`)

2. **Fuer jede Datei pruefen** ob die Aenderung korrekt ist (keine hardcoded Secrets, keine temporaeren Loesungen)

3. **Commit mit korrektem Message-Format:**
   ```
   fix(velero): Stop self-reference + empty velero-backups bucket + add opt-out annotation
   
   - Stopped velero deployment (eviction storm recovery)
   - Emptied 45G velero-backups bucket (Failed manual-verify backup)
   - Deleted .minio.sys/tmp/.trash (45G MinIO async deletion stuck)
   - Added backup.velero.io/backup-volumes-excludes annotation for minio-data
   - Corrected incident report (46G folder = live MinIO PVC, NOT orphaned staging)
   ```

4. **Push mit `[skip ci]`** (da keine Code-Aenderung, nur Infra/Docs):
   ```
   git push
   ```
   Hinweis: Das CI/CD-Workflow wird getriggert. Wenn es nur Docs/YAML-Aenderungen sind, kann `[skip ci]` im Commit-Message stehen.

5. **CI-Status pruefen:** Nach dem Push den GitHub Actions Status pruefen.

**Vorsicht:** NICHT pushen wenn: Secrets im Diff, temporaere Pfade, hardcoded IPs ohne Erklaerung.

---

## Prompt 6: Incident-Report finalisieren + Lektionen dokumentieren

Du bist Documentation-Agent. Der Incident-Report `docs/INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` muss finalisiert werden.

**Deine Aufgaben:**

1. **Status-Tabelle in §4 (Recovery) aktualisieren:**
   - R1: ✅ Velero gestoppt
   - R2: ✅ Failed Backup geloescht
   - R3: ✅ velero-backups Bucket geleert (44GiB → 0B)
   - R4: ⏳ Evicted-Pods (5342, GC laeuft)
   - R6: ⏳ App-Deployments (laufen teilweise, CNPG-Problem offen)

2. **§5 (Permanente Fixes) aktualisieren:**
   - F1 (Velero ephemeral-storage-Limit): ⬜ offen
   - F2 (Selbst-Referenz stoppen — opt-out Annotation): ⬜ offen
   - F3 (DB aus FS-Backup ausschliessen): ⬜ offen
   - F4 (Backup-Scope korrigieren): ⬜ offen
   - F5 (ephemeral-storage-Alert): ⬜ offen
   - F6 (kubelet-Reservierung): ⬜ offen
   - F7 (metrics-server k3s-Addon deaktivieren): ⬜ offen (benötigt k3s-Neustart)
   - F8 (CI/CD Pre-Deploy-Check): ⬜ offen

3. **§9 (Disk-Entlastung) mit den neuen Fakten ergaenzen:**
   - MinIO `mc rb` hat die Daten in `.minio.sys/tmp/.trash` verschoben
   - Trash-Purge hat nicht funktioniert (45G stuck)
   - Manuelle Loeschung via `rm -rf .trash/*` noetig
   - Disk von 96% → 72% nach Loeschung

4. **Neue Sektion §11: Lektionen** hinzufuegen:
   - `du /var/lib/kubelet/pods/*` zaehlt PVC-Daten via Bind-Mount DOPPELT
   - MinIO `mc rb --force` loescht NICHT sofort (async Trash)
   - Velero ephemeral-storage-Limit ist KRITISCH (ohne Limit = Eviction-Storm moeglich)
   - image-gc-threshold (75%) hilft NICHT wenn die Daten in PVCs sind (keine Images)

5. **Datei committen** (Prompt 5 uebernehmen lassen, oder separat `[skip ci]`)

**Dateien:** `docs/INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md`
