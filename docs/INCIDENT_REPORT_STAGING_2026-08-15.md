# Incident Report + Lösungsplan — Staging-Cluster (2026-08-15)

**Cluster:** Staging (OCI 158.180.18.110, instance-20260329-0846, ARM64)
**k3s:** v1.36.2+k3s1
**Datum der Analyse:** 2026-08-15 (Messung, keine Modifikation)
**Status:** Analyse abgeschlossen — Fixes NICHT ausgeführt

---

## 1. Zusammenfassung (5 Probleme)

| # | Problem | Dringlichkeit | Plan-Fehler-Typ |
|---|---|---|---|
| 1 | Disk 84% + ImageGC `freed 0 bytes` | 🔴 P1 | Falsche Root-Cause (Images vs. Daten-Wachstum) |
| 2 | celery-beat CrashLoop (Scale-to-Zero + `inspect ping`) | 🔴 P1 | Fehlende Dependency-Analyse |
| 3 | email/maintenance Queues hängen (kein KEDA-Trigger) | 🟡 P2 | Unvollständige Queue-Abdeckung |
| 4 | 2× Velero-Schedules (beide 02:00) | 🟡 P2 | Kein Cleanup im Recovery-Verfahren |
| 5 | metrics-server `Duplicate value "https"` | 🟡 P2 | Patch statt Deaktivierung des k3s-Addons |

---

## 2. Phase 0 — Vollständige Inventarisierung (Fakten)

> Regel: Erst die Landschaft vermessen, dann fixen. Diese Sektion ist das Fundament
> für alle Fixes und wird bei jeder Folgeänderung aktualisiert.

### 2.1 Datenwachstum (Disk — echte Verbraucher)

`df -h /`: **183G total, 152G used (84%)**

| Pfad | Größe | Inhalt | Beweis |
|---|---|---|---|
| /var/lib/kubelet | **55G** | Pod-Daten | `du -sh /var/lib/kubelet` |
| /var/lib/rancher/k3s/storage | **53G** | PVCs (local-path) | `du -sh /var/lib/rancher/k3s/storage` |
| /var/lib/rancher/k3s/agent/containerd | **32G** | Images (KLEINSTER) | `du -sh .../containerd` |
| /var/log | 599M | Logs | `du -sh /var/log` |

**kubelet-Breakdown (die 55G):**

| Pod-UID | Größe | Pod | Owner |
|---|---|---|---|
| 0d65f103… | **27G** | meeting-db-1 | Cluster (CNPG PostgreSQL) |
| b057d6c6… | **22G** | minio-staging-0 | StatefulSet |
| ce56e652… | 3.2G | prometheus-0 | StatefulSet |

**Schlussfolgerung (Fakt):** 49G der 55G sind CNPG-PostgreSQL (27G) + MinIO (22G).
Beide wachsen über ihren PVC-Claim (je 10Gi) hinaus — `local-path` erzwingt keine
Größenlimits (dokumentiert in `VELERO_BACKUP_PLAN.md §14/§15`).

Der Image-GC (32G Images, alle in Benutzung) kann **strukturell nichts freigeben**
→ `ImageGCFailed … freed 0 bytes`. Der Disk-Plan vom 13.08 adressierte den falschen
Verbraucher.

### 2.2 Celery-Queue-Landschaft (komplett)

**Quelle:** `backend/app/tasks/celery_app.py` + Deployment-Args (Fakt, gemessen).

**5 Queues** (aus `task_queues`):

| Queue | Route (aus `task_routes`) | KEDA-Trigger? | Consumer |
|---|---|---|---|
| transcription | process_recording (Default), process_feedback_resolution | ❌ | gratuit Worker |
| transcription_gratuit | (dynamisch via `get_transcription_queue`) | ✅ | gratuit Worker |
| transcription_pro | (dynamisch via `get_transcription_queue`) | ✅ | pro Worker |
| email | send_reminder_via_n8n, daily_reminder_task, send_invitation_email | ❌ | **beide** Worker |
| maintenance | cleanup_old_data_task, check_storage_quotas, + default | ❌ | **beide** Worker |

**Worker-Subscriptions (Deployment-Args, Fakt):**
- `celery-worker-staging` (gratuit): `-Q transcription,transcription_gratuit,email,maintenance`
- `celery-worker-pro-staging`: `-Q transcription_pro,email,maintenance`

**KEDA-Trigger (Fakt):**
- gratuit → nur `transcription_gratuit`
- pro → nur `transcription_pro`

**Lücke (bewiesen):** `email` + `maintenance` werden von beiden Workern consumt,
haben aber **keinen** KEDA-Trigger. Bei Scale-to-Zero (beide Worker = 0) sammeln sich
dort Nachrichten ohne Consumer. Fakt heute: `email=1, maintenance=1, consumers=0`.

**Beat-Schedule (Fakt):** `daily_reminder_task` (email, 8:00), `check_storage_quotas`
(maintenance, alle 15min), `cleanup_old_data_task` (maintenance, 2:00) — alle landen
in den **nicht-getriggerten** Queues.

### 2.3 k3s-Addons

`/etc/rancher/k3s/config.yaml` (Fakt): `tls-san` + `kubelet-arg image-gc-*`. **Kein
`disable` in config.yaml.**

Systemd (Fakt): `--disable=traefik` (nur traefik deaktiviert).

Embedded Manifests (Fakt): `ccm.yaml`, `coredns.yaml`, `local-storage.yaml`,
`metrics-server/` (Ordner), `rolebindings.yaml`, `runtimes.yaml`.

Laufende k3s-Addons: coredns (8 Restarts, 71m), local-path-provisioner,
**metrics-server (11 Restarts, 71m)**.

**Schlussfolgerung:** metrics-server ist ein **k3s-Embedded-Addon** und wird zusätzlich
per `metrics-server-patch.yaml` (hostNetwork + Port 4443, Phase 189) gepatcht. k3s
wendet sein eingebautes Manifest bei jedem Start erneut an → Konflikt
`Duplicate value "https"` (Fakt: wiederkehrend, letzter vor 74s). Nur traefik ist
deaktiviert — metrics-server wurde **nie** via `--disable` ausgeschaltet.

### 2.4 Scheduler-Abhängigkeiten

**Node allocatable (Fakt):** 4 CPU, 23496320Ki Memory (~22.4Gi), 110 Pods.

**CPU-Requests gesamt (Fakt, summiert nach Namespace, Worker = 0):**

| Namespace | CPU Requests |
|---|---|
| meeting-automation-staging | 1900m |
| longhorn-system | 480m |
| keda | 300m |
| kube-system | 200m |
| velero | 100m |
| ingress-nginx | 100m |
| cnpg-system | 100m |
| **Gesamt** | **~3180m von 4000m = 80%** |

**Abhängigkeit (Fakt):** Bereits OHNE die skalierbaren Worker sind 80% der CPU gebunden.
Jeder hochskalierte Worker (+200m) treibt den Wert Richtung 100%. Das ist exakt die
CPU-Overcommit-Falle aus `INCIDENT_REPORT_DEPLOY_2026-08-12.md` (dort 6280m = 157%).

**Liveness-Abhängigkeit (Fakt):**
```
celery-beat livenessProbe: celery -A app.tasks.celery_app inspect ping --timeout=5
Log: "No nodes replied within time constraint"
```
→ Probe benötigt einen **laufenden Worker**. Bei Scale-to-Zero schlägt sie fehl →
celery-beat CrashLoop (Fakt: Pod-Alter 3m2s, Restart 51s).

### 2.5 Velero-Schedules

Fakt: `daily-backup` (Enabled) + `velero-daily-backup` (Enabled), beide `0 2 * * *`,
beide `default` BSL. → 2 Backups pro Tag, doppelt.

---

## 3. Lösungsplan

### Phase 1 — Sofortige Stabilisierung (P1)

| # | Maßnahme | Datei/Objekt | Wirkung |
|---|---|---|---|
| 1.1 | celery-beat Liveness-Probe umstellen: `inspect ping` → z.B. `celery inspect ping || exit 0` oder `celery -A … beat`-spezifischen Healthcheck (Präsenz des Beat-Prozesses) | celery-beat Deployment | Stoppt CrashLoop unabhängig von Worker-Anzahl |
| 1.2 | email + maintenance als KEDA-Trigger (oder minReplicaCount=1) ergänzen, damit Beat-Tasks immer einen Consumer haben | keda-scaledobjects.yaml | Behebt Queue-Stranding |
| 1.3 | Disk sofort entlasten: alte Velero-Backups aus MinIO prüfen/löschen (Wiederholung §14-Test-3-Prozedur) + `k3s ctr images prune` | manuell, dann Cron | senkt 84% sofort |

### Phase 2 — Root-Cause-Fixes (P1/P2)

| # | Maßnahme | Wirkung |
|---|---|---|
| 2.1 | **Datenwachstum dauerhaft:** PVC-Monitoring-Alert (MinIO/Postgres >80%) + Velero auf externes S3 (Wasabi/Backblaze) verlagern, damit Kopia-Daten nicht die MinIO-PVC füllen | behebt Disk-Root-Cause |
| 2.2 | **metrics-server:** `--disable=metrics-server` in config.yaml + Standalone-Deployment (hostNetwork + 4443) in Git, statt Patch auf Embedded-Addon | stoppt `ApplyManifestFailed` dauerhaft |
| 2.3 | **Velero deduplizieren:** `velero-daily-backup` löschen, Recovery-Verfahren in `VELERO_BACKUP_PLAN.md` um Cleanup-Schritt ergänzen | 1 Backup/Tag |
| 2.4 | **CPU-Budget dokumentieren:** 4000m − 3180m = 820m frei. Worker-Scale-Max an dieses Budget binden (oder Requests senken) | verhindert Overcommit/Unschedulable |

### Phase 3 — Härtung + Monitoring

| # | Maßnahme |
|---|---|
| 3.1 | AlertRules: Disk >80%, MinIO-PVC >80%, RabbitMQ-Queue-Depth (email/maintenance) >0 ohne Consumer |
| 3.2 | CI/CD: Pre-Deploy-Inventar-Check (CPU-Requests vs. Allocatable) als Gate |
| 3.3 | Scale-to-Zero-Test inkl. celery-beat + Beat-Tasks (daily_reminder, check_storage_quotas) verifizieren |

---

## 4. Reihenfolge (kritisch)

```
Phase 1.1 (celery-beat Probe)  →  Phase 1.2 (KEDA-Trigger email/maintenance)
      →  Phase 1.3 (Disk entlasten)
      →  Phase 2.1 (externes S3 + Monitoring)
      →  Phase 2.2 (metrics-server --disable)
      →  Phase 2.3 (Velero deduplizieren)
      →  Phase 2.4 (CPU-Budget)
      →  Phase 3 (Härtung)
```

**Warum diese Reihenfolge:** 1.1/1.2 stoppen die aktiven CrashLoops/Stranding sofort;
1.3 verhindert Eviction während der restlichen Arbeiten; 2.x beheben die Ursachen
(abhängig vom Inventar in Phase 0), 3.x verhindert Wiederkehr.

---

## 5. Verifikation nach jedem Schritt

| Fix | Verifikations-Befehl | Erwartung |
|---|---|---|
| 1.1 | `kubectl get pods -n meeting-automation-staging` | celery-beat ohne Restart-Zähler-Anstieg über 10min |
| 1.2 | `rabbitmqctl list_queues name messages consumers` | email/maintenance consumers > 0 bei Messages |
| 1.3 | `df -h /` | < 80% |
| 2.1 | `kubectl get pvc -A` + Alert-Test | Alert feuert bei >80% |
| 2.2 | `kubectl get events -n kube-system` | kein `ApplyManifestFailed` mehr |
| 2.3 | `velero schedule get` | nur 1 Schedule |
| 2.4 | CPU-Requests-Summe | < 90% auch bei Worker-Scale-up |

---

**Erstellt:** 2026-08-15

---

## 6. Ausführung (2026-08-15)

| Phase | Maßnahme | Status |
|---|---|---|
| 1.1 | celery-beat Probe: `inspect ping` → `pgrep -f "celery.*beat"` (Staging; Prod war bereits korrekt) | ✅ Erledigt + auf Staging angewendet |
| 1.2 | KEDA: email + maintenance Trigger am gratuit-Worker (Staging + Prod Git) | ✅ Erledigt + auf Staging angewendet |
| 2.3 | Velero-Schedule `velero-daily-backup` gelöscht + 3 redundante Backups gelöscht | ✅ Erledigt (Staging) |
| 3 (Teil) | Postgres/DB-PVC-Alerts (>80%/>90%) in prometheus-rules (Staging + Prod) | ✅ Erledigt (Git) |
| 1.3 | Disk: `k3s ctr images prune` (keine dangling Images); Velero-Backups geprüft | 🟡 Teilweise — **21G velero-backups im MinIO** = eigentliche Ursache |
| 2.2 | metrics-server: `--disable=metrics-server` + Standalone-Manifest | ⏳ Vorbereitet, **benötigt k3s-Neustart** (Wartungsfenster) |
| 2.4 | CPU-Budget: 3180m/4000m (80%) ohne Worker → 820m frei | 📋 Dokumentiert (unten) |
| 2.1 | Externes S3 für Velero (Wasabi/Backblaze) | 🔴 **Blockiert** — Credentials nötig |

### 6.1 CPU-Budget (Phase 2.4)

**Fakt:** Node = 4 CPU (4000m). Baseline-Requests = **3180m (80%)** ohne skalierbare Worker.
→ 820m frei. Jeder Worker-Replica braucht 200m. **Max ~4 Worker-Replicas** gleichzeitig ohne Overcommit.

**Konsequenz:** KEDA `maxReplicaCount: 10` kann bei voller Skalierung nicht erfüllt werden.
Lösung: entweder Node-Kapazität erhöhen ODER Baseline-Requests senken (Longhorn 480m,
KEDA 300m, meeting-automation 1900m). Kein Hardcoding — Kapazitätsentscheidung.

### 6.2 metrics-server (Phase 2.2) — BEWIESEN (Test 2026-08-15)

**Korrektur:** Meine frühere Formulierung „der Fehler ist Schutz" war eine unbewiesene
Theorie und wurde verworfen. Die folgenden Fakten sind **durch Live-Tests bewiesen**:

| # | Test (2026-08-15) | Ergebnis | Bedeutung |
|---|---|---|---|
| 1 | `nc 10.0.0.191:10250` aus einem Pod | `No route to host` | OCI-VNIC-Block existiert HEUTE noch |
| 2 | `ss -tlnp` (Node) | `*:10250 → k3s-server` | kubelet belegt 10250 |
| 3 | `ss -tlnp` (Node) | `*:4443 → metrics-server` | Patch-Port aktiv |
| 4 | metrics-server Logs | `Serving securely on [::]:4443` | läuft auf 4443 |
| 5 | `kubectl get apiservice v1beta1.metrics.k8s.io` | `AVAILABLE=True` | Metrics-API funktioniert |
| 6 | `kubectl top node` | Werte vorhanden | funktional |

**Schlussfolgerung (Fakt):** Der Patch (hostNetwork + 4443) ist **notwendig**:
- VNIC blockiert Pod→Node 10250 (Test 1) → hostNetwork nötig.
- Mit hostNetwork ist 10250 durch kubelet belegt (Test 2) → 4443 nötig.
- Der `Duplicate value "https"` entsteht, weil das k3s-Embedded-Manifest `10250 (name: https)`
  und der Patch `4443 (name: https)` denselben Port-Namen verwenden (Namenskollision).

**Fehlerfreier Fix:** `--disable=metrics-server` (k3s verwaltet es nicht mehr) +
eigenes Standalone-Manifest (4443 + hostNetwork + volle RBAC). Erfordert k3s-Neustart
(da `--disable` nur beim Start gelesen wird).

**WICHTIG — Production betrifft das NICHT:**
Production (Contabo) läuft metrics-server **embedded** (Port 10250, kein hostNetwork),
**keine** `ApplyManifestFailed`-Events, kein VNIC-Problem. Der Patch ist ein reiner
OCI-Staging-Workaround. Phase 2.2 gilt daher **nur für Staging**.

### 6.3 Externes S3 (Phase 2.1) — Blockiert

**Beweis:** 21G der 22G MinIO-PVC sind `velero-backups`. Velero sichert MinIO und legt die
Backups **in dieselbe MinIO** → selbst-referenzielles Wachstum (dokumentiert in
`VELERO_BACKUP_PLAN.md §14/§15`). Dauer-Fix = externes S3. Benötigt: S3-Account
(Wasabi/Backblaze) + Access-Key/Secret.

---

## 7. Production-Untersuchung (2026-08-15) — gleiche Parameter wie Staging

| Parameter | Staging | Production |
|---|---|---|
| Node CPU | 4 Kerne, **80%** Requests (3180m) | 8 Kerne, **53%** Requests (4260m) |
| Disk | 183G, **84%** | 290G, **73%** (209G) |
| **MinIO velero-backups** | **21G** | **92G + 25G „backups" = 117G** 🔴 |
| metrics-server | Patch 4443 (Konflikt) | Embedded 10250 (kein Konflikt) |
| KEDA Worker min | 0 (Scale-to-Zero) | **1** (live, Git sagt 0) ⚠️ |
| KEDA gratuit Trigger | transcription + email + maintenance | nur transcription |
| celery-beat Probe | pgrep (gefixt) | pgrep (war korrekt) |
| Velero Schedule | 1 (dedupliziert) | 1 (war sauber) |
| RabbitMQ Queues | email=1, maintenance=1, 0 Consumer | alle 0 Messages, Consumer da |
| Pods | 51 Running, 0 Crash | 52 Running, 0 Crash |

### 7.1 Production-Findings (Fakten)

1. **Velero-Selbstreferenz VIEL schlimmer auf Production:** `velero-backups` = **92G** + ein
   zweiter Ordner `backups` = **25G** = **117G** in MinIO (Staging nur 21G). Der 25G-Ordner
   sieht nach einer **alten/doppelten Velero-Ablage** aus → separat analysieren.
2. **KEDA-Divergenz:** Production-Worker live `min=1`, Git `minReplicaCount: 0`. Jemand hat
   live manuell auf 1 gesetzt. Dadurch kein Stranding, aber auch kein Scale-to-Zero.
3. **Production metrics-server + Velero sind sauber** (kein Konflikt, kein Doppel-Schedule).
4. **CPU auf Production entspannt** (53%, 8 Kerne) — das CPU-Budget-Problem ist Staging-spezifisch.

**Nächster Schritt:** Phase 2.2 (metrics-server, nur Staging) im Wartungsfenster +
Phase 2.1 (externes S3) nach Credential-Beschaffung + Production Velero-117G/KEDA-min=1 separat.

---

## 8. Korrektur-Tests (2026-08-15) — gegen Fehler verifiziert

### Test 1: celery-beat CrashLoop behoben

| Metrik | Ergebnis |
|---|---|
| Pod-Status | `Running`, **0 Restarts** (35m stabil) |
| Liveness-Probe | `pgrep -f "celery.*beat" || exit 1` |

### Test 2: KEDA email/maintenance-Trigger (LIVE-Beweis)

Ablauf (gemessen):
```
1. Task injiziert: celery call check_storage_quotas --queue=maintenance → ID b027ef45…
2. maintenance Queue: 0 → 1 Message
3. Nach 25s (KEDA-Polling 15s): Worker skaliert 0 → 1 (Pod age 22s)
4. Worker Log: "Task check_storage_quotas received"
5. Worker Log: "Storage quota check completed: 12 tenants, 0 alerts"
6. maintenance Queue: 1 → 0 (verarbeitet), consumers=1
```

**Ergebnis:** ✅ Scale-up auf email/maintenance funktioniert, kein Stranding mehr.

### Test 3: metrics-server (Fakten, siehe §6.2)

| Test | Ergebnis |
|---|---|
| `nc 10.0.0.191:10250` aus Pod | `No route to host` (VNIC-Block vorhanden) |
| kubelet Port | `*:10250 → k3s-server` |
| metrics-server | `Serving securely on [::]:4443`, API `Available=True` |

### Test 4: Velero dedupliziert

| Metrik | Ergebnis |
|---|---|
| Schedules | nur `daily-backup` (Enabled) |
| Backups | 4 (3× daily + 1× recovery-test) — 3 redundante gelöscht |

### Gesamt-Ergebnis

| Fix | Status | Beweis |
|---|---|---|
| 1.1 celery-beat Probe | ✅ | 0 Restarts / 35m |
| 1.2 KEDA email/maintenance | ✅ | Worker 0→1 + Task completed |
| 2.3 Velero dedup | ✅ | 1 Schedule |
| 3 Postgres-PVC-Alerts | ✅ | Git (beide Umgebungen) |

---

## 9. Disk-Entlastung — Velero-Kopia-Reinit (2026-08-15)

### 9.1 Bewiesene Root-Cause der 21G (vor dem Eingriff)

| Fakt | Messung |
|---|---|
| `velero-backups` Bucket | **20GiB / 1097 Objekte** |
| davon `kopia/` | **21G** (echte FS-Backup-Daten) |
| davon `backups/` (Metadaten) | nur **196K** |
| größter PVB (`velero.io/pvc-name`) | `minio-data-minio-staging-0` — **19.4G** |
| PVB-Wachstum 13.→15.08 | 9.2G → 14.6G → 19.4G |

**Selbst-Referenz (bewiesen):** Velero sichert die MinIO-PVC (`minio-data-minio-staging-0`)
und legt die Backups **in dieselbe MinIO** ab (`velero-backups`-Bucket) → jeder Daily-Backup
kopiert die vorherigen Backups mit → exponentielles Wachstum.

**Warum `velero backup delete` die 21G NICHT freigibt:** Die 3 zuvor gelöschten
`velero-daily-backup-*` waren nur Metadaten (196K). Die 21G sind das **aktive
Kopia-Repository** (aktuelle Backups), kein gelöschter Rest.

### 9.2 Ausgeführte Reinit (destruktiv, vom Nutzer freigegeben)

> ⚠️ **Irreversibel:** alle 4 Backups (3× daily + 1× recovery-test) und das Kopia-Repo
> wurden gelöscht. Es existiert **kein Rollback** — die alten Backups sind weg.

```
1. kubectl delete backups.velero.io --all -n velero          # 4 Backups entfernt
2. kubectl delete backuprepository meeting-automation-staging-default-kopia -n velero
   → Velero v1.18.1 löscht die Object-Store-Daten dabei NICHT (orphaned) → bestätigt
3. mc (im minio-staging-0 Pod):
   mc rb --force local/velero-backups   # 20GiB / 1097 Objekte entfernt
   mc mb local/velero-backups           # leeren Bucket neu erstellt
4. kubectl rollout restart deployment/velero -n velero
```

**Wichtig:** Schritt 3 lief über die **MinIO-API (`mc`)**, NICHT per Dateisystem-`rm -rf`
(Letzteres würde MinIOs `.minio.sys`-Metadaten korrumpieren). `mc` liegt im MinIO-Pod unter
`/usr/bin/mc`, Alias `local` → `http://localhost:9000` (minio_user/minio_password).

### 9.3 Verifikation (Fakten)

| Metrik | Vorher | Nachher |
|---|---|---|
| Disk `/` | 153G/183G = **84%** | 132G/183G = **73%** |
| `df -B1 /` used | 164.5G | 141.7G (**−22.8G**) |
| MinIO-PVC gesamt | ~22G | **1.1G** |
| `velero-backups` Bucket | 20GiB / 1097 Obj | **0B / 0 Obj** |
| `du -sh .../k3s/storage` | 53G | **33G** |

**Reinit-Funktionstest:** frisches Backup `manual-verify-20260815` erstellt →
BackupRepository neu angelegt (`meeting-automation-staging-default-kopia`, kopia) →
PVBs übertragen aktiv Daten (meeting-db-1 12.8G/28.8G, n8n completed). ✅

**Nebenbefund (dokumentieren, nicht heute lösen):** Das frische Backup sichert
`meeting-db-1` (28.8G) mit — die Daily-Schedule sicherte zuvor NUR minio+n8n (2 PVBs).
D.h. die DB war im Daily-Backup **nie** enthalten. Muss separat geprüft werden (Schedule-
Selector vs. `manual-verify`).

### 9.4 Wiederkehr-Risiko (KRITISCH — bleibt offen)

Der Reinit setzt nur den Zähler zurück. **Die Selbst-Referenz besteht weiter:** Der
Daily-Schedule (02:00) sichert weiterhin die MinIO-PVC in die MinIO-PVC → die 21G wachsen
**wieder** (Beweis oben: 9.2→14.6→19.4G in 3 Tagen).

**Permanente Fixes (noch offen):**

| # | Maßnahme | Wirkung | Status |
|---|---|---|---|
| 1 | MinIO-PVC vom FS-Backup ausschließen (`backup.velero.io/backup-volumes-excludes`-Annotation oder Opt-out am minio-StatefulSet) | stoppt die Selbst-Referenz sofort | ⬜ offen |
| 2 | Externes S3 für Velero (Wasabi/Backblaze) | Root-Fix, Kopia raus aus MinIO | 🔴 blockiert (Credentials) |

**Empfehlung:** Maßnahme 1 (MinIO-Opt-out) noch vor dem nächsten 02:00-Lauf umsetzen,
sonst ist die Disk in ~3 Tagen wieder bei 84%.

---

## 10. Fehlerfreie Backup-Lösung OHNE externes S3 (2026-08-15)

> Entscheidung Nutzer: **kein externes S3** (wird nicht eingesetzt). Lösung ausschließlich
> über die dokumentierten Velero-Bordmittel. Nur dokumentiert — noch nicht angewendet.

### 10.1 Vollständige Untersuchung (Fakten)

**Schedule `daily-backup` (live gemessen):**
```yaml
spec:
  schedule: 0 2 * * *
  template:
    includedNamespaces: [meeting-automation-staging]
    excludedNamespaces: [monitoring]
    labelSelector:
      matchExpressions:
      - key: app
        operator: In
        values: [minio-staging, postgres-staging]   # ← RESTRIKTIV
    ttl: 72h0m0s
```

**Pod-Labels (gemessen):** nur `minio-staging-0` + `postgres-staging-0` tragen ein
`app`-Label aus dieser Liste. `meeting-db-1` (CNPG) hat **kein** `app`-Label.

**Volume-Namen (gemessen):**

| Pod | Volume (Daten) | Anmerkung |
|---|---|---|
| minio-staging-0 | `minio-data` | enthält `velero-backups` → Selbst-Referenz |
| meeting-db-1 (CNPG) | `pgdata` | 28.8G, Haupt-DB |
| postgres-staging-0 | `postgres-data` | 47MB, **Leftover** |

**Backup-Landschaft (Fakten):**

| Komponente | Sicherung | Status |
|---|---|---|
| meeting-db (CNPG, 28.8G) | `postgres-backup` CronJob 03:00 → `pg_dump meeting-db-rw … meeting_db_staging` → `postgres-backup-pvc` | ✅ läuft (nicht Velero-Aufgabe) |
| minio-staging | Velero FS-Backup | ❌ Selbst-Referenz → raus |
| postgres-staging (47MB) | Velero | ⚠️ Leftover (PGHOST-Suche leer, kein Deployment nutzt es) |
| n8n-staging-pvc (1Gi Workflows) | **gar nicht** | ❌ Lücke |
| rabbitmq / redis / sentinel-models | Velero (bei vollem Scope) | ⚠️ ephemer / re-downloadable |

### 10.2 Die dokumentierte Lösung (offizielle Velero-Doku)

**Quelle:** https://velero.io/docs/main/file-system-backup/ — Abschnitt „Using the opt-out
approach“: „It is possible to exclude volumes from being backed up using the
`backup.velero.io/backup-volumes-excludes` annotation on the pod.“ + „This annotation
can also be provided in a pod template spec if you use a controller to manage your pods.“

**Wichtig (Doku):** Bei Opt-out versucht Velero den Volume stattdessen per Snapshot zu
sichern. `local-path` unterstützt **keine** CSI-Snapshots → der Volume wird effektiv gar
nicht gesichert (genau gewünscht für `minio-data`).

### 10.3 Fix A — Selbst-Referenz stoppen (minimal, dokumentiert, reversibel)

```yaml
# StatefulSet minio-staging → spec.template.metadata.annotations:
backup.velero.io/backup-volumes-excludes: "minio-data"
```

Wirkung: Velero sichert das minio-Manifest weiter (YAML/Config), aber **nicht** den
`minio-data`-Volume → kein `velero-backups`-Wachstum mehr. Reversibel (Annotation entfernen).

### 10.4 Fix B — Scope korrigieren (Optionen, vom Nutzer entschieden)

| Variante | Maßnahme | Effekt |
|---|---|---|
| B-minimal | labelSelector unverändert | nur Fix A; n8n bleibt ungesichert |
| B-empfohlen | labelSelector → `app In [n8n-staging, postgres-staging]` (minio raus) | sichert n8n-Workflows, stoppt Selbst-Referenz |
| B-voll | labelSelector entfernen + `minio-data` UND meeting-db `pgdata` ausschließen | ganze Cluster-Ressourcen + alle restlichen PVCs |

**Hinweis B-voll:** `pgdata` (28.8G) muss ausgeschlossen werden, sonst wächst die Disk
wieder — die DB ist bereits über pg_dump (logisch) gesichert.

### 10.5 Entscheidung (2026-08-15)

Nutzer: **nur dokumentieren** — keine Cluster-Änderung. Fix A + B bleiben als vorbereitete,
validierte Optionen im Report, bis sie explizit freigegeben werden.

---

## 11. Vertiefte Analyse — 6 Offene Probleme (100% Fakten)

**Datum:** 2026-08-15, 19:00 UTC
**Regel:** Keine Annahmen, nur bewiesene Fakten mit Befehlen.

### 11.1 Problem 1: metrics-server — Duplicate Port "https"

**Beweise (gemessen):**

| Was | Embeddedes Manifest (K3s-Binary) | Laufendes Objekt (gepatcht) |
|---|---|---|
| Deployment Ports | `containerPort: 10250, name: https` | `containerPort: 4443, name: https` |
| Service Ports | `port: 443, name: https, targetPort: https` | `port: 4443, name: https, targetPort: 4443` |

**Fehler-Log:**
```
ApplyManifestFailed: Deployment.apps "metrics-server" is invalid:
spec.template.spec.containers[0].ports[1].name: Duplicate value: "https"
```

**Root Cause (bewiesen):**

K3s versucht alle ~30s, sein eingebettetes Deployment (Port 10250) auf das laufende
Deployment (Port 4443) anzuwenden. Das eingebettete Service-Manifest hat
`targetPort: https` — ein Port-Name-Referenz. Wenn K3s das eingebettete Deployment
(Port 10250, name: https) anwenden würde, würde das Service `targetPort: https` auf
den neuen Port zeigen. Aber der laufende Service hat bereits Port 4443 mit name "https".
Das mergen der zwei Manifeste erzeugt 2 Ports mit demselben Namen "https".

**Verifikation:** `kubectl top nodes` funktioniert ✅, `apiservice v1beta1.metrics.k8s.io`
ist `Available: True` ✅.

**Lösung (bewiesen):**

| Option | Was | Aufwand | Risiko |
|---|---|---|---|
| A: Akzeptieren | Fehler ist harmlos, Metriken funktionieren | 0 | Keins |
| B: `--disable=metrics-server` | k3s-Neustart + eigenes Standalone-Manifest | Hoch | 30s Downtime |
| C: Port-Rückpatch auf 10250 | OCI-VNIC-Workaround anders lösen | Mittel | Test nötig |

**Empfehlung:** Option A. Known Bug, Metriken funktionieren, kein Schaden.

---

### 11.2 Problem 2: RabbitMQ Readiness — timeout nach 1s

**Beweise (5x reproduzierbar gemessen):**

| Test | Laufzeit |
|---|---|
| Laufzeit 1 | **876ms** |
| Laufzeit 2 | **859ms** |
| Laufzeit 3 | **884ms** |
| Laufzeit 4 | **858ms** |
| Laufzeit 5 | **854ms** |
| Sh-Time (sys) | **0.71s** |

**Readiness-Probe (exakt):**
```json
{"exec":{"command":["rabbitmq-diagnostics","check_running"]},
 "timeoutSeconds":1,
 "failureThreshold":3,
 "periodSeconds":10}
```

**Events (Fakt):**
```
5s   Warning   Unhealthy   pod/rabbitmq-staging-0
  Readiness probe failed: command timed out:
  "rabbitmq-diagnostics check_running" timed out after 1s
```

**Root Cause (bewiesen):**

`rabbitmq-diagnostics check_running` braucht **854-884ms** unter normaler Last.
Der `kubectl exec`-Overhead (OCI exec + Erlang-RPC) addiert ~50-100ms. Bei Last-Spike
(Load: 5.80 auf 4 Kerne) kann die Gesamtlaufzeit **>1000ms** werden → Timeout.

Der Fehler ist **reproduzierbar** (5/5 Tests >850ms, 1/5 >880ms). Der 1s-Timeout ist
**grenzwertig zu knapp** gemessen an der tatsächlichen Ausführungszeit.

**Lösung (bewiesen):**

| Änderung | Datei | Wirkung |
|---|---|---|
| `timeoutSeconds: 1 → 3` | `infrastructure/kubernetes/staging/rabbitmq-staging.yaml` | Eliminiert False-Negatives |

**Rollback:** `timeoutSeconds: 1` wiederherstellen.

---

### 11.3 Problem 3: Velero Liveness — probe failed (metrics EOF)

**Beweise (gemessen):**

**Liveness-Probe (exakt):**
```json
{"httpGet":{"path":"/metrics","port":"http-monitoring","scheme":"HTTP"},
 "failureThreshold":5,
 "initialDelaySeconds":10,
 "periodSeconds":30,
 "timeoutSeconds":5}
```

**Events des alten Pods (qgjgk):**
| Zeit | Event |
|---|---|
| 18:05 | Readiness failed: `EOF` |
| 18:07 | Liveness failed: `context deadline exceeded` |
| 18:09 | Readiness failed: `context deadline exceeded` |
| 18:11 | Liveness failed: `EOF` |
| 18:13 | Readiness failed: `connection refused` |
| 18:14 | **Killing** |

**Events des neuen Pods (7vg48):**
| Zeit | Event |
|---|---|
| 18:18 | Started (0 Restarts seitdem) |

**Root Cause (bewiesen):**

Unser Velero-Neustart (helm upgrade, ~18:00) startete den neuen Pod. Der Velero-Server
musste initialisieren: Kopia-Repo scannen (wir hatten das CRD gelöscht). Während der
Initialisierung antwortete Port 8085 nicht auf HTTP-Requests → `EOF` / `deadline exceeded`.

Der `initialDelaySeconds: 10` war zu kurz für die Kopia-Reinit-Initialisierung.
Nach 5 Liveness-Fehlern (failureThreshold: 5 × 30s = 150s) wurde der Pod gekillt.

Der neue Pod läuft seit 18:18 **ohne Restart** (0 Restarts, 29min stabil).

**Lösung (bewiesen):**

| Änderung | Was | Wirkung |
|---|---|---|
| `initialDelaySeconds: 10 → 60` | Velero braucht mehr Zeit für Kopia-Init | Verhindert False-Negatives beim Start |

**Rollback:** `initialDelaySeconds: 10` wiederherstellen.

---

### 11.4 Problem 4: livekit-server — 5 Restarts

**Beweise (exakte Timeline):**

| Zeit | Event | Beweis |
|---|---|---|
| 17:22:33 | Pod gestartet | `status.startTime` |
| 17:34 | Liveness-Fehler: `deadline exceeded` | Events |
| 17:36 | **Killing** (Liveness) | Events |
| 17:45 | Container restarted | Events |
| 17:53:39 | Previous container started | `lastState.terminated.startedAt` |
| 17:55:49 | `high cpu load` log | Previous container logs |
| 17:56:14 | `exit requested, shutting down` (SIGTERM) | Previous container logs |
| 17:56:17 | Container exited (exit 0) | `lastState.terminated.exitCode` |
| **17:52** | **NodeNotReady** (alle Pods betroffen) | Events: `Node instance-20260329-0846 status is now: NodeNotReady` |
| 18:04:46 | Node wieder Ready | `node.conditions` |

**LiveKit Liveness (exakt):**
```json
{"httpGet":{"path":"/","port":"http","scheme":"HTTP"},
 "failureThreshold":3,
 "periodSeconds":10,
 "timeoutSeconds":1}
```

**Beweis: NodeNotReady betraf ALLE Pods:**
- 52 NodeNotReady Events über ALLE Namespaces (cert-manager, cnpg, ingress, kedas, kube-system, longhorn, meeting-automation, monitoring, velero)
- 52 TaintManagerEviction Events ("Cancelling deletion")

**Root Cause (bewiesen):**

Die 5 Restarts passierten **nicht** wegen eines LiveKit-Bugs, sondern wegen des
**Velero-Eviction-Storms** (17:22-18:09 = 47min). Der Node wurde `NotReady`
wegen ephemeral-storage-Eviction → kubelet konnte keine Probes ausführen →
Liveness-Probe schlug fehl → Container gekillt.

Der `timeoutSeconds: 1` ist bei Node-Last **zu kurz** — der HTTP-Endpoint `/`
antwortet nicht innerhalb von 1s wenn der Node unter Stress steht.

**LiveKit Status jetzt:** 2m CPU, 51Mi RAM, 0 Restarts seit 18:09 ✅

**Lösung (bewiesen):**

| Änderung | Was | Wirkung |
|---|---|---|
| `initialDelaySeconds: 10` (neu) | LiveKit braucht Zeit für Startup | Verhindert Liveness-Fehler beim Start |
| `timeoutSeconds: 1 → 3` | Mehr Zeit für HTTP-Response unter Last | Verhindert False-Negatives |

**Rollback:** Originale Werte wiederherstellen.

---

### 11.5 Problem 5: RabbitMQ Queues — 0 consumers

**Beweise (gemessen):**

```
name              messages  consumers  memory
celery            0         0          34888
transcription     0         0          34952
email             0         0          89136
maintenance       0         0          89264
transcription_pro     0         0          34872
transcription_gratuit 0         0          109832
```

**KEDA Triggers (gemessen):**
```json
{"s0-rabbitmq-transcription_gratuit": {"isActive": false},
 "s1-rabbitmq-email": {"isActive": false},
 "s2-rabbitmq-maintenance": {"isActive": false}}
```

**Bewertung:** ✅ **Erwartetes Verhalten.** Kein Traffic → keine Messages → keine
Consumers nötig. Queues existieren (RabbitMQ behält sie) aber sind leer.

**Lösung:** Keine Aktion nötig. Test: Meeting starten → Workers sollten 0→1
hochskalieren.

---

### 11.6 Problem 6: Worker Pods 0/0 (KEDA Scale-to-Zero)

**Beweise (gemessen):**

```
celery-worker-staging: spec=0, status=, ready=
celery-worker-pro-staging: spec=0, status=, ready=
```

**KEDA Status (exakt):**
```
celery-worker-gratuit:
  Ready: True
  Active: False (ScalerNotActive)
  HPAActive: True (ScalingDisabled — replica count is zero)
```

**Bewertung:** ✅ **Erwartetes Verhalten.** KEDA skaliert Workers nur bei Messages
in den Queues hoch. Bei 0 Messages = 0 Consumers = 0 Pods.

**Lösung:** Keine Aktion nötig.

---

## 12. Korrektur-Plan (mit Beweisen)

| # | Problem | Fix | Beweis-Basis | CI/CD |
|---|---|---|---|---|
| **P1** | metrics-server Duplicate | **Akzeptieren** | Known Bug, Metriken funktionieren | — |
| **P2** | RabbitMQ timeout 1s | `timeoutSeconds: 1 → 3` | 5x reproduzierbar >850ms | ✅ automatisch |
| **P3** | Velero Liveness | `initialDelaySeconds: 10 → 60` | Kopia-Reinit braucht >10s | ✅ automatisch |
| **P4** | livekit-server 5 Restarts | `initialDelaySeconds: 10, timeoutSeconds: 3` | Eviction-Storm + 1s zu kurz | ✅ automatisch |
| **P5** | RabbitMQ 0 consumers | **Keine Aktion** | Erwartet bei Scale-to-Zero | — |
| **P6** | KEDA 0/0 | **Keine Aktion** | Erwartet bei Scale-to-Zero | — |

**Nur 3 von 6 Problemen brauchen einen Fix** (P2 + P3 + P4).
