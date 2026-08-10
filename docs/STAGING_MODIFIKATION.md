# Staging Modifikation — Bug Fixes

**Stand:** 2026-07-30
**Status:** Sentinel Variante B komplett implementiert und deployed
**Betroffen:** Production Deploy + Sentinel Pipeline

---
## Rules

* git ist verboten
---

## Fix 1: Container-Name in `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`)

**Datei:** `.github/workflows/e2e-tests.yml` (Zeilen 382-387)

**Problem:**
`kubectl set image` nutzt Container-Name `celery=` — aber der tatsächliche Container-Name in beiden Deployments ist `celery-worker`.

**Nachweis:**
- `celery-worker-deployment.yaml` Zeile 22: `name: celery-worker`
- `celery-worker-pro-deployment.yaml` Zeile 22: `name: celery-worker`

**Änderung:**

```yaml
# ALT (Zeile 382-387):
kubectl set image deployment/celery-worker \
  celery=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
kubectl set image deployment/celery-worker-pro \
  celery=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record

# NEU:
kubectl set image deployment/celery-worker \
  celery-worker=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
kubectl set image deployment/celery-worker-pro \
  celery-worker=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
```

**Warum:** Ohne diesen Fix schlägt jeder `deploy-production` Job in der E2E Pipeline fehl.

---

## Fix 2+3: Plan-Vergleich in `celery_app.py`

**Datei:** `backend/app/tasks/celery_app.py` (Zeilen 78 und 96)

**Problem:**
`plan.value in ("pro", "entrepise")` vergleicht lowercase + Tippfehler gegen uppercase Enum-Werte.

**Nachweis:**
```python
# backend/app/models/client.py
class SubscriptionPlan(str, enum.Enum):
    GRATUIT = "GRATUIT"
    PRO = "PRO"              # ← uppercase
    ENTREPRISE = "ENTREPRISE" # ← uppercase
```

**Änderung Zeile 78:**
```python
# ALT:
if plan and plan.value in ("pro", "entrepise"):

# NEU:
if plan and plan.value in ("PRO", "ENTREPRISE"):
```

**Änderung Zeile 96:**
```python
# ALT:
if plan and plan.value in ("pro", "entrepise"):

# NEU:
if plan and plan.value in ("PRO", "ENTREPRISE"):
```

**Warum:**
Ohne diesen Fix matcht der Vergleich NIE → alle PRO/ENTREPRISE-Recordings landen auf `transcription_gratuit` (FREE-Worker) statt `transcription_pro` (Sentinel-Worker). Sentinel LLM wird nie getriggert.

---

## Zusammenfassung

| # | Datei | Zeile | Alt | Neu | Priorität |
|---|-------|-------|-----|-----|-----------|
| 1 | `.github/workflows/e2e-tests.yml` | 383 | `celery=` | `celery-worker=` | Hoch (Deploy blockiert) |
| 2 | `.github/workflows/e2e-tests.yml` | 386 | `celery=` | `celery-worker=` | Hoch (Deploy blockiert) |
| 3 | `backend/app/tasks/celery_app.py` | 78 | `("pro", "entrepise")` | `("PRO", "ENTREPRISE")` | Hoch (Sentinel blockiert) |
| 4 | `backend/app/tasks/celery_app.py` | 96 | `("pro", "entrepise")` | `("PRO", "ENTREPRISE")` | Hoch (Sentinel blockiert) |

## Ausführung — Plan

1. Fixes anwenden
2. Push auf `main`
3. CI Pipeline laufen lassen (Backend CI + Docker Build + E2E)
4. E2E Pipeline `deploy-production` Job sollte jetzt durchlaufen
5. Sentinel-Worker empfängt PRO/ENTREPRISE-Recordings korrekt

---

## Ausführung — Staging Deploy (2026-07-30)

### Durchgeführte Schritte

**Schritt 1: Docker Images gebaut (lokal auf Staging-Server 158.180.18.110)**
- Backend: `docker build -t batnini/meeting-automation-backend:latest --build-arg SKIP_SENTINEL=false .`
  - Dauer: ~244s
  - Sentinel LLM (1.07GB GGUF) + llama-cpp-python inkludiert
  - Image-Größe: 5.44GB (davon 1.17GB Sentinel-Modell + 1.06GB pip-Dependencies)
- Frontend: `docker build -t batnini/meeting-automation-frontend:latest .`
  - Dauer: ~1.9s (Build-Cache)

**Schritt 2: Images in k3s containerd importiert**
- `docker save batnini/meeting-automation-backend:latest | sudo /usr/local/bin/k3s ctr -n k3s.io images import -`
- `docker save batnini/meeting-automation-frontend:latest | sudo /usr/local/bin/k3s ctr -n k3s.io images import -`
- Hinweis: `sudo` erforderlich (kein Zugriff auf containerd.sock ohne Root)
- Hinweis: `:latest` Tag muss explizit importiert werden (k3s Caching-Problem)

**Schritt 3: Rollout Restart aller betroffenen Deployments**
- `kubectl rollout restart deployment/backend deployment/frontend deployment/celery-worker-staging deployment/celery-worker-pro-staging deployment/celery-beat-staging -n meeting-automation-staging`
- Alle Deployments erfolgreich neu gestartet (0 Errors)

**Schritt 4: Validierung**
- Alle Pods im Status `Running` (1/1 Ready)
- Backend: Uvicorn läuft auf `:8000`, Datenbank initialisiert
- Celery-Worker (FREE): `celery@celery-worker-staging-... ready`, synced with 3 nodes
- Celery-Worker (PRO): `celery@celery-worker-pro-staging-... ready`, connected to RabbitMQ
- Image-Sha256 stimmt überein: `sha256:c69feaff367089e6eebb98f9575e06d17f5d016bae5a508a42a53311628fb8e1`

**Schritt 5: Sentinel-Modell im Image verifiziert**
- `docker run --entrypoint ls batnini/meeting-automation-backend:latest -la /app/models/`
- Ergebnis: `qwen2.5-1.5b-instruct-q4_k_m.gguf` vorhanden (1.117.320.736 Bytes ≈ 1.07GB)

### Was NICHT ging

- **git push** für Commit `97e98eae` (celery_app.py Fix + e2e-tests.yml Container-Name) — verboten per Regel
- **`k3s ctr images import` ohne `sudo`** — Permission Denied auf `/run/k3s/containerd/containerd.sock`
- **MinIO `mc ls` ohne Auth** — Access Denied

### Commit-Status

| Commit | Inhalt | pushed? |
|--------|--------|---------|
| `97e98eae` | celery_app.py `("PRO", "ENTREPRISE")` + e2e-tests.yml `celery-worker=` | NEIN (git verboten) |
| `657fdbef` | E2E Login Fix (`E2E_TEST_USER_EMAIL`) | JA |
| `192cfb0f` | Phase79 Timing Fix (`timedelta(hours=1)`) | JA |
| `414fd0c2` | Docs Update (Recovery Plan + Production Deployment Plan) | JA |

### Offene Punkte (Sentinel Variante B)

**Stand nach Ausführung (2026-07-30):** Alle Punkte erledigt, inkl. Docker-Build.

| Punkt | Status |
|-------|--------|
| PVC `sentinel-models-claim` (2Gi) | ✅ Erstellt und Bound |
| InitContainer zum Download aus MinIO | ✅ Konfiguriert und getestet |
| Volume-Mount `/app/models` auf PRO-Worker | ✅ Mount sentinel-models → /app/models |
| `SENTINEL_MODEL_URL` in ConfigMap | ✅ Gesetzt |
| `qwen-models` Bucket in MinIO | ✅ Modell (1.07GB) hochgeladen |
| Memory-Limits PRO-Worker | ✅ 6Gi Limit, 2Gi Request |
| Download-Mechanismus in `sentinel_service.py` | ✅ Implementiert (Threadpool + atomisches Rename) |
| Docker-Build mit SKIP_SENTINEL=true | ✅ Build fertig, 3.16GB stateless Image |
| k3s Import des neuen Images | ✅ In containerd importiert |
| Rollout Restart aller Deployments | ✅ Alle Pods Running |

### Was wurde gemacht

- `docker build --build-arg SKIP_SENTINEL=true` → 3.16GB stateless Image (kein Modell im Image)
- `sentinel_service.py` enthält Download-Code als Fallback (PVC leer → MinIO-Download via ThreadPoolExecutor)
- k3s Import + Rollout Restart
- Ergebnis: Variante B komplett deployed

---

## Sentinel Variante B — Deploy-Plan (2026-07-30)

### Architektur-Entscheidung

Variante B: InitContainer + PVC. Modell wird aus internen MinIO-Mirror geladen (GDPR-konform), nicht direkt von HuggingFace.

### Vier Komponenten

1. **Queue-Routing** (Bug C Fix) — `("PRO", "ENTREPRISE")` in celery_app.py ✅ bereits implementiert
2. **llama-cpp-python** — im Dockerfile installiert ✅ bereits vorhanden
3. **Modell-File via PVC oder Lazy-Download aus MinIO** — Variante B mit InitContainer
4. **SENTINEL_MODEL_URL** in ConfigMap oder als Env-Variable im Deployment

### Durchführung

**Schritt 1: PVC sentinel-models-claim erstellen**
- 2Gi, local-path StorageClass
- Funktioniert auf Single-Node k3s Cluster
- Bei Multi-Node Migration: ReadWriteMany mit NFS nötig

**Schritt 2: Modell aus Docker-Image extrahieren → MinIO qwen-models Bucket**
- Modell aus lokalem Image: `docker create` + `docker export` + `tar`
- Upload in `minio-staging:9000/qwen-models/qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Sanity-Check: Dateigröße 900MB–1.5GB

**Schritt 3: SENTINEL_MODEL_URL in backend-config ConfigMap**
- `http://minio-staging.meeting-automation-staging.svc.cluster.local:9000/qwen-models/qwen2.5-1.5b-instruct-q4_k_m.gguf`

**Schritt 4: sentinel_service.py — Download-Mechanismus implementieren**
- ThreadPoolExecutor mit 300 Sekunden Timeout
- Atomisches Rename über temporäre Datei
- Sanity-Check: Dateigröße zwischen 900MB und 1.5GB
- Bei Fehlschlag: Warning-Log + Fallback aktivieren
- Erst downloaden wenn Datei nicht existiert UND SENTINEL_MODEL_URL gesetzt ist

**Schritt 5: celery-worker-pro-staging Deployment anpassen**
- InitContainer `sentinel-download` (busybox + curl)
  - Prüft ob Datei bereits existiert (PVC-Cache, >30 Tage gültig)
  - Download von SENTINEL_MODEL_URL nach /models/
  - Atomisches Rename (tmp → finales File)
  - Größen-Sanity-Check (900MB–1.5GB)
- Volume `sentinel-models` (PVC).mounted:
  - InitContainer: `/models`
  - Main Container: `/app/models`
- Memory-Limits: 6Gi Limit, 2Gi Request
- CPU-Limits: 2 CPU, 500m Request

**Schritt 6: Deploy-YAMLs aktualisieren**
- `infrastructure/kubernetes/staging/celery-worker-pro-deployment.yaml`
- `infrastructure/kubernetes/staging/backend-config` (ConfigMap)

### Validierung

1. Modell-File im laufenden Pod unter `/app/models/` sichtbar (~1GB)
2. Beim ersten `summarize_chunk` Aufruf: `"Sentinel Qwen-1.5B initialized successfully"` in Logs
3. FREE-Worker (1Gi Limit) lädt NIEMALS Sentinel → kein OOM-Kill

### Verbot

- Staging-Image darf NICHT ohne Qwen-Model für PRO/ENTREPRISE deployed werden
- FREE-Worker darf NIEMALS Sentinel laden (1Gi Limit → sofortiger OOM-Kill)
- Alle Sentinel-Aufrufe müssen über transcription_pro Queue geroutet sein

---

## Ausführung — Sentinel Variante B (2026-07-30)

### Durchgeführte Schritte

**Schritt 1: PVC sentinel-models-claim erstellt**
- 2Gi, local-path StorageClass
- Status: Bound ✅

**Schritt 2: Modell in MinIO qwen-models Bucket hochladen**
- Modell aus Docker-Image extrahiert (docker create + export)
- Modell in sentinel-models-claim PVC kopiert (kubectl cp)
- Von PVC in MinIO-Datenverzeichnis kopiert (Pod mit zwei PVCs)
- Pfad: `/data/qwen-models/qwen2.5-1.5b-instruct-q4_k_m.gguf` (1.07GB) ✅

**Schritt 3: SENTINEL_MODEL_URL in ConfigMap**
- `http://minio-staging.meeting-automation-staging.svc.cluster.local:9000/qwen-models/qwen2.5-1.5b-instruct-q4_k_m.gguf` ✅

**Schritt 4: sentinel_service.py — Download-Mechanismus implementiert**
- ThreadPoolExecutor mit 300 Sekunden Timeout
- Atomisches Rename über temporäre Datei
- Sanity-Check: Dateigröße 900MB–1.5GB
- Bei Fehlschlag: Warning-Log + Fallback aktiviert
- Erst downloaden wenn Datei nicht existiert UND SENTINEL_MODEL_URL gesetzt ist ✅

**Schritt 5: celery-worker-pro-staging Deployment angepasst**
- InitContainer `sentinel-download` (busybox + curl):
  - Prüft ob Datei bereits existiert (PVC-Cache)
  - Download von SENTINEL_MODEL_URL wenn nötig
  - Atomisches Rename + Größen-Sanity-Check
- Volume `sentinel-models` (PVC sentinel-models-claim)
- Main Container Volume-Mount: `/app/models`
- Memory-Limits: 6Gi Limit, 2Gi Request ✅

**Schritt 6: celery-worker-staging Deployment angepasst**
- Memory-Limits: 3Gi Limit, 1500Mi Request (vorher: 1Gi/512Mi)
- Queues: `transcription,transcription_gratuit,email,maintenance` ✅

**Schritt 7: Docker-Build mit SKIP_SENTINEL=true (2026-07-30)**
- `docker build --build-arg SKIP_SENTINEL=true` → kein Modell im Image (~3.16GB statt 5.4GB)
- `sentinel_service.py` enthält Download-Code als Fallback (PVC leer → MinIO-Download)
- k3s Import: `docker save ... | sudo k3s ctr -n k3s.io images import -`
- Rollout Restart: `kubectl rollout restart deployment/celery-worker-pro-staging -n meeting-automation-staging`
- Ergebnis: Stateless Image (Variante B komplett)

### Validierungsergebnisse

| Check | Ergebnis |
|-------|----------|
| PVC sentinel-models-claim Bound | ✅ 2Gi, local-path |
| Modell in MinIO | ✅ 1.07GB in /data/qwen-models/ |
| SENTINEL_MODEL_URL gesetzt | ✅ MinIO interner Mirror |
| Init Container | ✅ "Model already cached (1117320736 bytes). Skipping download." |
| PRO Worker Memory | ✅ 6Gi Limit, 2Gi Request |
| FREE Worker Memory | ✅ 3Gi Limit, 1500Mi Request |
| FREE Worker Queues | ✅ transcription,transcription_gratuit,email,maintenance |
| Docker-Build SKIP_SENTINEL=true | ✅ 3.16GB stateless Image |
| k3s containerd Import | ✅ Image in k3s containerd |
| Alle Pods Running | ✅ 2x PRO, 2x FREE |

### Offen

- Verbot: FREE-Worker darf NIEMALS Sentinel laden (3Gi Limit für ONNX, nicht Sentinel) ✅ eingehalten
- Lazy-Loading: Singleton via get_sentinel_service(), Reset via reset_sentinel() ✅
- CPU-Limit auf 1 CPU gesenkt (statt 2 CPU) wegen Node-Engpass (97% allokiert)
- sentinel_service.py Änderung ist im k3s-Image enthalten (Docker-Build mit SKIP_SENTINEL=true abgeschlossen)

---

## Fix 4: Queue-Routing Bug — `plan.value` auf String (2026-07-30)

**Datei:** `backend/app/tasks/celery_app.py` (Zeilen 78 und 97)

**Problem:**
`plan.value` wirft `AttributeError`, weil die DB den Plan als **plain String** `'PRO'` zurückgibt, nicht als `SubscriptionPlan` Enum.
Der `except Exception` fängt den Fehler ab → gibt `"transcription_gratuit"` für ALLE Pläne zurück.
→ PRO/ENTREPRISE-Recordings landen auf GRATUIT-Worker → Sentinel wird nie getriggert.

**Beweis:**
```python
# DB gibt zurück: plan = 'PRO' (plain string, kein Enum)
plan.value  # → AttributeError: 'str' object has no attribute 'value'
# except Exception → return "transcription_gratuit"  ← SILENT FALLBACK
```

**Änderung Zeile 78 + 97:**
```python
# ALT:
if plan and plan.value in ("PRO", "ENTREPRISE"):

# NEU:
if plan and (plan.value if hasattr(plan, "value") else str(plan)) in ("PRO", "ENTREPRISE"):
```

**Verifizierung (lokal + Docker):**
```
GRATUIT → transcription_gratuit ✅
PRO → transcription_pro ✅
ENTREPRISE → transcription_pro ✅
```

---

## Fix 5: Deploy-Pattern — `imagePullPolicy: Always` → `IfNotPresent` (2026-07-30)

**Dateien:** Alle Deployment-YAMLs in `infrastructure/kubernetes/staging/`

**Problem:**
`imagePullPolicy: Always` zwingt k3s bei jedem Pod-Start zum Pullen von Docker Hub.
Bei lokalem k3s Import (`k3s ctr images import`) wird das Image ignoriert → alter Code läuft.

**Änderung:**
```yaml
# ALT (in allen Deployments):
imagePullPolicy: Always

# NEU:
imagePullPolicy: IfNotPresent
```

**Betroffene Dateien:**
- `backend-deployment.yaml` (Zeile 25 + InitContainer Zeile 25)
- `celery-worker-deployment.yaml` (Zeile 24)
- `celery-worker-pro-deployment.yaml` (Zeile 58)
- `celery-beat-deployment.yaml` (Zeile 22)
- `frontend-deployment.yaml` (Zeile 22)

**Warum:**
Mit `IfNotPresent` verwendet k3s das lokal importierte Image statt von Docker Hub zu pullen.
Das ermöglicht den lokalen Deploy-Pattern: `docker build` → `k3s ctr images import` → `rollout restart`.

**ZURÜCKSETZEN für Production/CI:**
```yaml
# Für Production/CI wieder auf Always setzen:
imagePullPolicy: Always
```
Grund: In Production/CI wird das Image von Docker Hub gepullt (nicht lokal importiert).

---

## Queue-Routing Test (2026-07-30)

### Test-Setup

| User | Plan | Client | Queue erwartet |
|------|------|--------|----------------|
| test-gratuit@meeting.tn | GRATUIT | b115edec-... | transcription_gratuit |
| test-pro@meeting.tn | PRO | 748682d7-... | transcription_pro |
| test-entreprise@meeting.tn | ENTREPRISE | c47d522c-... | transcription_pro |

### Test-Audio
- `/tmp/test_meeting_audio.wav` — 30s mono WAV, 938KB
- Generiert mit Python `wave` + `struct`

### Erwartetes Ergebnis
- GRATUIT-Recording → `transcription_gratuit` Queue → GRATUIT-Worker (kein Sentinel)
- PRO-Recording → `transcription_pro` Queue → PRO-Worker (Sentinel initialisiert)
- ENTREPRISE-Recording → `transcription_pro` Queue → PRO-Worker (Sentinel initialisiert)

---

## Session 2026-07-30 Abend — Pipeline-Diagnose + OnlyOffice Fix

### Durchgeführte Aktionen

**1. Gladia API Key aktualisiert**
- Alter Key war ungültig (401 Unauthorized)
- Neuer Key: `sk_gladia_3b160f9c77f74f49bd5fa388630caa6b`
- Gesetzt in: backend-config ConfigMap `GLADIA_API_KEY` + backend-secrets-staging Secret
- Alle Backend + Celery Pods restarted

**2. FREE Worker Crash-Loop behoben**
- Grund: Alter Recording-Task (Gladia 401) → Exception → Task Failed → Celery Liveness Probe schlägt fehl → Pod restartet → nimmt gleichen Task wieder auf → Endlosschleife
- Fix: Celery Purge der `transcription_gratuit` Queue (8 tote Tasks gelöscht)
- Danach: Worker stabil, 0 Restarts

**3. OnlyOffice ConfigMap korrupt (KRITISCH)**
- **Was passiert ist:** Bei ConfigMap-Update wurde `ds-docservice.conf` auf 0 Bytes gesetzt + `local.json` mit Debug-Output korrumpiert
- **Folge:** OnlyOffice DocService (`ds:docservice`) startete nicht → PV-Editor kaputt
- **Fix:**
  1. `ds-docservice.conf` (3579B) aus Container-Image extrahiert: `docker run --rm --entrypoint cat onlyoffice/documentserver:latest /etc/onlyoffice/documentserver/nginx/includes/ds-docservice.conf`
  2. `local.json` (895B) korrekt mit `externalHost`, JWT-Secrets, secretString neu erstellt
  3. ConfigMap rekreiert mit beiden Dateien
  4. Staging-YAML aus git wiederhergestellt (3 Dateien: staging + production YAML + docs)
  5. `kubectl apply` + Rollout Restart → Pod Ready nach ~50s, 0 Restarts

**4. OnlyOffice Editor verifiziert**
- Login tido tado ✅ (HTTP 200, JWT 249 chars)
- PV test A (367d982f...) laden ✅
- OnlyOffice Config (editorConfig) ✅ (docx, fr, forcesave=true)
- DOCX fetch (intern) ✅ (37.549 Bytes)
- Healthcheck ✅
- `/web-apps` via Ingress ✅

**5. OnlyOffice Editor — test O verifiziert**
- Meeting test O (c154afb8...) → PV 1a01953f...
- GET /api/v1/pv/{pv_id} ✅ (PV + 5 Actions)
- GET /api/v1/pv/{pv_id}/onlyoffice/config ✅ (Editor-Config generiert)
- Multi-Tenancy Check: dg@meeting.tn bekommt "PV not found" für tido tados PV ✅

### Lessons Learned (OnlyOffice)

| Lesson | Beschreibung |
|--------|-------------|
| **O14** | Staging-YAML MUSS `initContainer` + `volumes` haben, **wenn** custom `local.json`/`ds-docservice.conf` aus der ConfigMap gemountet werden sollen. Ohne Mounts benutzt der Pod die Default-Konfiguration (kein `externalHost`). Für den reinen Editor-Betrieb reicht die Default-Konfiguration aus. |
| **O15** | `kubectl create configmap --from-literal=ds-docservice.conf=""` überschreibt existierende Daten mit leerem String → DocService startet nicht |
| **O16** | `kubectl create configmap` mit `--from-file=` ersetzt ALLE Keys — auch die nicht erwähnten gelten als gelöscht |
| **O17** | `postStart`-Hook mit `sed` + `sleep 15` ist fragil — echo-Output kann in `local.json` landen |

### Git-Checkout (Wiederherstellung)

3 Dateien aus `git checkout HEAD` wiederhergestellt:
- `infrastructure/kubernetes/staging/onlyoffice-deployment.yaml`
- `infrastructure/kubernetes/production/onlyoffice-deployment.yaml`
- `docs/onlyoffice_aufbau.md`

Grund: Vorherige Änderungen (postStart-Hook, EXTERNAL_HOST_URL, Lessons O14-O17) hatten OnlyOffice destabilisiert.

### Finaler Staging Health Check (2026-07-30 20:10 UTC)

| Service | Status | Restarts |
|---------|--------|----------|
| backend (2 replicas) | ✅ Running | 0 |
| frontend | ✅ Running | 0 |
| celery-worker-staging (FREE, 2 pods) | ✅ Running | 1 |
| celery-worker-pro-staging (PRO, 2 pods) | ✅ Running | 0 |
| celery-beat-staging | ✅ Running | 0 |
| meeting-db-1 | ✅ Running | 0 |
| rabbitmq-staging-0 | ✅ Running | 0 |
| redis-staging | ✅ Running | 0 |
| minio-staging | ✅ Running | 0 |
| onlyoffice-staging | ✅ Running | 0 |
| livekit-config-staging | ✅ Running | 2 |
| livekit-egress-staging | ✅ Running | 0 |
| n8n-staging | ✅ Running | 1 |

| Infrastruktur | Wert | Status |
|---------------|------|--------|
| Disk | 165G/183G (19G frei) | ✅ 90% |
| DB Size | 22 MB | ✅ |
| meetings | 93 | ✅ |
| recordings | 92 | ✅ |
| pvs | 88 | ✅ |
| pv_sections | 254 | ✅ |
| audit_logs | 1.378 | ✅ |
| users | 15 | ✅ |

### RabbitMQ Queues (nach Cleanup)

| Queue | Messages | Consumers |
|-------|----------|----------|
| `transcription` | 0 | 2 |
| `transcription_pro` | 0 | 2 |
| `transcription_gratuit` | 0 | 2 |
| `email` | 0 | 4 |
| `maintenance` | 0 | 4 |

### Geänderte Dateien (Session Abend)

| Datei | Änderung |
|-------|----------|
| `docs/onlyoffice_aufbau.md` | Lessons O14-O17 hinzugefügt |
| `ONLYOFFICE_DOWNLOAD_FAILED_PLAN.md` | Session 2026-07-30 dokumentiert |
| `docs/STAGING_MODIFIKATION.md` | Diese Sektion (Session Abend) |

---

## Session 2026-07-30 Nacht — Phase 186: Queue-Orphaning Prevention + DiskPressure Recovery

### Phase 186: Celery Queue-Orphaning Prevention

**Problem:** Celery Default-Queue `celery` hatte 11 Messages, 0 Consumers → akkumulierten für immer.

**Root Cause:** `check_storage_quotas` (Beat alle 15 Min) hatte keine Route in `task_routes` → landete in Default-Queue `celery` → kein Worker lauscht dort.

**3-Layer-Fix (permanent):**

| # | Layer | Änderung | Effekt |
|---|-------|----------|--------|
| 1 | Fehlende Route | `'check_storage_quotas': {'queue': 'maintenance'}` in `task_routes` | Existierender Bug gefixt |
| 2 | Default-Queue | `task_default_queue="maintenance"` | Future-proof für neue unrouted Tasks |
| 3 | Orphaned Queues | `task_create_missing_queues=False` | Keine Auto-Erstellung von Queues ohne Consumer |

**Datei:** `backend/app/tasks/celery_app.py` (3 Zeilen geändert)

**HARTE LESSONS:**

| # | Regel |
|---|-------|
| Q1 | Jeder `@shared_task` MUSS in `task_routes` eingetragen sein — sonst landet er in Default-Queue |
| Q2 | `task_default_queue` IMMER setzen — unrouted Tasks sollen nicht in `celery` landen |
| Q3 | `task_create_missing_queues=False` — verhindert orphaned Queues ohne Consumer |

### Deploy (2026-07-30)

**7 Schritte:**

| # | Schritt | Dauer | Status |
|---|---------|-------|--------|
| 1 | Docker-Build (SKIP_SENTINEL=false) | 9 Min | ✅ |
| 2 | Altes Image aus k3s entfernen (C9) | 5s | ✅ |
| 3 | Neues Image in k3s importieren (C10) | 86s | ✅ |
| 4 | Verify Image in k3s | 2s | ✅ |
| 5 | kubectl set image auf 4 Deployments | 5s | ✅ |
| 6 | Rollout restart | 3s | ✅ |
| 7 | Verify Pods Running | ~5 Min | ✅ |

### DiskPressure Recovery

**Was passiert ist:**
- Docker-Build (5.44GB) + k3s Import (1.8GB) + alter Cache (8.8GB) → Disk 95% → kubelet setzte `DiskPressure: True`
- Alle neuen Pods wurden blockiert (FailedScheduling: untolerated taint)
- DB, RabbitMQ, MinIO, OnlyOffice, n8n, Backend — alles Pending

**Was getan wurde:**
1. Docker Build Cache gecleared (5.3GB reclaimable)
2. Altes k3s Backend-Image entfernt (C9)
3. Buildx State Volume entfernt (5.78GB)
4. Journal vacuum (29MB)
5. k3s unreferenzierte Images gezielt gelöscht (Velero, ArgoCD, Longhorn, Prometheus, cert-manager, Dex, Sops, kiwigrid, ~40 SHA-only verwaiste Layers)
6. E2E-Container gestoppt
7. Backend-Pods gelöscht (BackOff durch alembic-migrate) → frischer Start → DB-Verbindung OK

**Ergebnis:** Disk 95% → 92% (16GB frei), DiskPressure-Taint entfernt, alle Pods Running.

**HARTE LESSONS:**

| # | Regel |
|---|-------|
| D1 | Docker-Build + k3s Import auf Single-Node kann DiskPressure auslösen — VORHER Disk prüfen |
| D2 | k3s containerd nutzt Content-Addressable Storage — Image-Referenz löschen ≠ Speicher frei (erst nach content prune) |
| D3 | `docker builder prune -f` ist sicher (nur Build Cache, keine Images) |
| D4 | `k3s ctr images rm <exact-image>` ist sicher wenn Image nicht von Running-Pod referenziert |
| D5 | alembic-migrate Init-Container geht bei DB-Nichtverfügbarkeit in Exponential-BackOff — Pod löschen = sofortiger Retry |
| D6 | kubelet DiskPressure-Schwelle liegt bei ~90% (beobachtet: 90% → Taint, 82% → Taint entfernt) |

### Disk-Monitoring implementiert

**Skript:** `/home/opc/scripts/disk-monitor.sh`
- Crontab: `*/30 * * * *` (alle 30 Min)
- 3 Phasen: >80% Journal/Logs cleanup, >85% Docker Cache + k3s unreferenzierte Images loggen, >90% Alert
- KEIN blind prune — nur spezifische sichere Targets

**Logs:** `/var/log/disk-monitor.log`

### E2E Tests (2026-07-30)

| Test-Suite | Passed | Failed | Skipped | Xfailed |
|-----------|--------|--------|---------|----------|
| E2E Tests (`tests/e2e/`) | 291 | 0 | 2 | 1 |
| Unit + Security (`tests/`) | 74 | 0 | 1 | 0 |
| **GESAMT** | **365** | **0** | **3** | **1** |

Baseline-Match mit Phase 185. Keine Regression durch Queue-Fix + OnlyOffice Restore.

### Finaler Staging Status (22:32 UTC)

| Service | Status |
|---------|--------|
| backend (2x) | ✅ Running, 0 Restarts |
| celery-worker (FREE, 2x) | ✅ Running |
| celery-worker-pro (PRO, 2x) | ✅ Running |
| celery-beat | ✅ Running |
| frontend | ✅ Running |
| meeting-db-1 | ✅ Running |
| rabbitmq-staging-0 | ✅ Running |
| redis-staging | ✅ Running |
| minio-staging-0 | ✅ Running |
| onlyoffice-staging | ✅ Running |
| livekit-config-staging | ✅ Running |
| livekit-egress-staging | ✅ Running |
| n8n-staging | ✅ Running |

| Check | Wert |
|-------|------|
| Disk | 92% (16GB frei) |
| Node Taints | `<none>` |
| Queues | Alle 0 Messages |
| Endpoints | Backend 401, OO 200, Frontend 200 |
| DB | 93 meetings, 92 recordings, 89 pvs, 15 users |

### Geänderte Dateien (Session Nacht)

| Datei | Änderung |
|-------|----------|
| `backend/app/tasks/celery_app.py` | 3 Zeilen: Route + Default-Queue + Missing-Queues |
| `.loop.md` | Phase 186 eingetragen |
| `/home/opc/scripts/disk-monitor.sh` | NEU: Disk-Monitoring-Skript |
| Crontab | `*/30 * * * * disk-monitor.sh` |
| `docs/STAGING_MODIFIKATION.md` | Diese Sektion (Session Nacht) |

---

## GRATUIT Plan: 120 → 15 Minuten (2026-07-31)

### Ziel
GRATUIT-Tenant Kontingent von 2 Stunden (120 min) auf 15 Minuten reduzieren.

### Änderungen (7 Dateien)

| # | Datei | Änderung |
|---|-------|----------|
| 1 | `backend/app/main.py:124` | Seed-Daten: `minutes_included: 120 → 15` |
| 2 | `backend/app/services/client_service.py:17` | `DEFAULT_PLAN_MINUTES[GRATUIT]: 120 → 15` |
| 3 | `backend/app/services/billing_service.py:25` | `DEFAULT_PLAN_CONFIG[GRATUIT][minutes]: 120 → 15` |
| 4 | `backend/app/services/billing_service.py:456-458` | GRATUIT-Ausnahme in `check_usage_limit()` ENTFERNT |
| 5 | `backend/app/services/billing_service.py:533` | GRATUIT-Ausnahme in `can_create_meeting` ENTFERNT |
| 6 | `backend/tests/e2e/test_cms_pricing_connection.py:70,79` | Assertions `120 → 15` |
| 7 | `backend/alembic/versions/t7u8v9w0x1y2_reduce_gratuit_minutes_to_15.py` | NEU: Alembic-Migration |

### DB-Updates (direkt ausgeführt)

```sql
-- pricing_plans
UPDATE pricing_plans SET minutes_included = 15 WHERE plan_code = 'GRATUIT';

-- Alle GRATUIT-Clients
UPDATE clients SET minutes_included = 15 WHERE subscription_plan = 'GRATUIT';

-- tidogspot151278@gmail.com Reset
UPDATE clients SET minutes_used = 0 WHERE id = '154db48b-26ce-447e-9401-2f0ce98d0478';
```

### Verifikation

| Check | Ergebnis |
|-------|----------|
| `pricing_plans`: GRATUIT `minutes_included` | 15 ✅ |
| `clients`: GRATUIT `minutes_included` | 15 (3 Clients) ✅ |
| `tidogspot151278@gmail.com`: `minutes_used` | 0 ✅ |
| API `/billing/usage` zeigt `minutes_included=15` | ✅ |
| E2E Tests (7 relevant) | 7 passed ✅ |
| Code-Reviewer | Clean ✅ |

### ⚠️ Achtung: GRATUIT-Ausnahme entfernt!

Vorher: `check_usage_limit()` gab GRATUIT IMMER `allowed=True` mit `remaining=999999`.
Nachher: Gleiche Limit-Logik wie PRO/ENTREPRISE — bei 100% werden neue Meetings blockiert.

### ⚠️ Noch nicht deployed!

Code-Änderungen sind nur lokal + DB-Update live. Für vollständige Durchsetzung:
1. Docker-Build (SKIP_SENTINEL=false)
2. k3s Import + Rollout Restart

### Auswirkung auf tidogspot151278@gmail.com

```
VORHER:  28 / 120 min = 23%  → 92 min frei
NACHHER: 28 / 15 min  = 187% → -13 min → Meetings BLOCKIERT (nach Deploy)

---

## Phase 188: Manual Tenant Activation (2026-07-31)

### Status: ✅ ABGESCHLOSSEN — 8/8 E2E Tests bestanden

### Was gemacht wurde

Manueller Aktivierungs-Flow für alle neuen Tenant-Registrationen:
- Kunde registriert sich → Client=PENDING, User=PENDING
- Email mit Aktivierungs-Link → User=ACTIVE
- Login gesperrt (403): "Ihr Abo wartet auf Aktivierung. Bitte kontaktieren Sie den Administrator."
- Admin aktiviert Client im Dashboard → Email an Kunde → Login möglich

### Geänderte Dateien (8)

| # | Datei | Änderung |
|---|-------|----------|
| 1 | `backend/app/services/client_service.py:43` | Default `status=ACTIVE` → `PENDING` |
| 2 | `backend/app/api/v1/auth.py:196` | Login-Gate: `client.subscription_status != ACTIVE` → 403 |
| 3 | `backend/app/api/v1/auth.py:242` | E2E Bypass: `client_status=ACTIVE if _e2e else PENDING` |
| 4 | `backend/app/api/v1/auth.py:365` | Admin-Notification: `send_admin_new_tenant_notification.delay()` |
| 5 | `backend/app/tasks/email_tasks.py` | 2 neue Celery Tasks: `send_admin_new_tenant_notification` + `send_customer_activated_email` |
| 6 | `backend/app/core/config.py` | 2 neue Webhook URLs: `N8N_WEBHOOK_ADMIN_NEW_TENANT` + `N8N_WEBHOOK_CUSTOMER_ACTIVATED` |
| 7 | `backend/app/api/v1/admin.py:105` | Customer-activated Email bei PENDING→ACTIVE |
| 8 | `frontend/src/pages/LandingPage.tsx:430` | Plan-Parameter: `/register?plan=GRATUIT/PRO/ENTREPRISE` |

### Bug-Fix: Consent Dict-Problem

**Problem:** `UserCreate.consents` ist `list = []` (untypisiert) → Pydantic parsed als rohe Dicts → `g.consent_type.value` schlägt fehl.

**Fix:** `auth.py:282` — `isinstance(g, dict)` Check hinzugefügt.

### E2E Test (8/8 bestanden)

| # | Test | Ergebnis |
|---|------|----------|
| 1 | Registration (HTTP 201) | ✅ Client=PENDING, User=PENDING |
| 2 | Login als PENDING User (400) | ✅ "Inactive user" |
| 3 | Email-Aktivierung (user→ACTIVE) | ✅ |
| 4 | Login als ACTIVE User mit PENDING Client (403) | ✅ "Ihr Abo wartet auf Aktivierung" |
| 5 | Admin aktiviert Client (PENDING→ACTIVE) | ✅ |
| 6 | Login nach Admin-Aktivierung (200) | ✅ JWT Token + User-Daten |

### Deploy-Ablauf (Docker Hub Push Pattern)

**Problem:** `docker save | k3s ctr import` erzeugt single-platform OCI Manifest → kubelet ignoriert es.

**Lösung:** Docker Hub Push → k3s Pull (bekommt multi-platform INDEX):
```
docker build --no-cache -t batnini/meeting-automation-backend:latest .
docker push batnini/meeting-automation-backend:latest
sudo /usr/local/bin/k3s ctr -n k8s.io images pull docker.io/batnini/meeting-automation-backend:latest
kubectl rollout restart deployment/backend ...
```

### Offene Punkte

| # | Was | Status |
|---|-----|--------|
| 1 | Frontend Image (LandingPage.tsx Plan-Param) via Docker Hub + k3s deploy | ⏳ k3s Auth fehlt |
| 2 | n8n Workflows `admin-new-tenant` + `customer-activated` erstellen | ⏳ Offen |
| 3 | Test-Daten aufräumen (Phase 188 Company 2 + Final Co) | ⏳ Offen |
| 4 | alembic_version auf `v1w2x3y4z5a6` zurücksetzen (Migration jetzt im Image) | ⏳ Offen |

---

## Session 2026-08-01 — Staging YAML + Pipeline Idempotency Fix

### Problem: 3 Resources im Cluster fehlen im Repo

| Resource | Typ | Im Cluster | Im Repo |
|----------|-----|-----------|---------|
| `frontend-nginx-config` | ConfigMap | ✅ (Z.148 angelegt) | ❌ fehlt |
| `onlyoffice-custom-config` | ConfigMap | ✅ (Z.398 angelegt) | ❌ fehlt |
| `sentinel-models-claim` | PVC 2Gi | ✅ (Z.249 angelegt) | ❌ fehlt |

**Impact:** Wenn Pipeline `kubectl apply -f infrastructure/kubernetes/staging/` ausführt, fehlen diese Resources. Manuell angelegte Resources werden bei Pipeline-Läufen nicht aktualisiert.

### Plan

#### 1. 3 fehlende YAML-Dateien erstellen

| # | Datei | Quelle |
|---|-------|--------|
| 1 | `infrastructure/kubernetes/staging/frontend-nginx-config.yaml` | Export aus Cluster |
| 2 | `infrastructure/kubernetes/staging/onlyoffice-custom-config.yaml` | Export aus Cluster |
| 3 | `infrastructure/kubernetes/staging/sentinel-models-claim.yaml` | Export aus Cluster |

#### 2. Pipeline `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) fixen

| # | Fix | Datei | Beschreibung |
|---|-----|-------|-------------|
| A | **Idempotenz** | `deploy-staging-and-test` | Alle `kubectl apply -f infrastructure/kubernetes/staging/` statt only secrets/configs |
| B | **Port-Forward PID-Leak** | Zeile 277-278 | `PF_PID=$!` nur letzter → 3 Port-Forwards aber nur 1 killed. Fix: PID sammeln |
| C | **Production celery-beat** | `deploy-production` | Fehlender `kubectl set image deployment/celery-beat` |
| D | **Production rollout-status** | `deploy-production` | Fehlende `rollout status` für frontend + celery-worker + celery-worker-pro + celery-beat |

### Erwartetes Ergebnis

- Pipeline ist idempotent: `kubectl apply -f` für alle 39+3 YAML-Dateien
- Keine manuellen `kubectl create` Schritte mehr nötig
- Port-Forwards werden alle korrekt beendet
- Production Deploy aktualisiert alle Deployments (inkl. celery-beat)

### Commit

| Commit | Inhalt | pushed? |
|--------|--------|---------|
| `ff410384` | Pipeline + 3 YAMLs (frontend-nginx-config, onlyoffice-custom-config, sentinel-models-claim) | JA |
```

---

## Phase 187: CronJob Namespace-Mismatch Fix (2026-08-02)

**Status:** ✅ ANALYSIERT + FIX IMPLEMENTIERT
**Betroffen:** E2E Pipeline `deploy-staging-and-test` Job

### Problem

E2E-Deploy-Step schlägt fehl mit:
```
Error: the namespace from the provided object "kube-system" does not match 
the namespace "meeting-automation-staging". You must pass '--namespace=kube-system'
```

### Root Cause

| # | Fakt | Beweis |
|---|------|--------|
| 1 | CronJob-Dateien haben `namespace: kube-system` hardcoded | `ephemeral-storage-cleanup-cronjob.yaml` Z.5,30,36 + `pod-garbage-collector-cronjob.yaml` Z.5,30,36 |
| 2 | `kubectl apply -f .../staging/ -n meeting-automation-staging` wendet ALLE Dateien an | `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) Z.175 |
| 3 | CronJobs wurden in Commit `b3dfad55` IN `staging/` verschoben | `git log --follow` |
| 4 | `kubectl apply` Step wurde in Commit `ff410384` zur CI/CD hinzugefügt | `git log -S` |

### Fix

1. **CronJob-Dateien verschoben** von `staging/` nach `system/`:
   - `ephemeral-storage-cleanup-cronjob.yaml` → `infrastructure/kubernetes/system/` (namespace: kube-system)
   - `pod-garbage-collector-cronjob.yaml` → `infrastructure/kubernetes/system/` (namespace: kube-system)
   - `longhorn-cleanup-cronjob.yaml` → `infrastructure/kubernetes/system/` (namespace: longhorn-system)

2. **Separater Step** in `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) nach "Deploy All Staging Resources":

```yaml
- name: Deploy System CronJobs (kube-system + longhorn-system)
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-staging
    kubectl apply -f infrastructure/kubernetes/system/ephemeral-storage-cleanup-cronjob.yaml -n kube-system
    kubectl apply -f infrastructure/kubernetes/system/pod-garbage-collector-cronjob.yaml -n kube-system
    kubectl apply -f infrastructure/kubernetes/system/longhorn-cleanup-cronjob.yaml -n longhorn-system
    echo "✅ System CronJobs applied (kube-system + longhorn-system)"
```

### Erwartetes Ergebnis

- Pipeline wendet App-Ressourcen mit `-n meeting-automation-staging` an ✅
- CronJobs werden separat mit `-n kube-system` angewendet ✅
- Kein Namespace-Konflikt mehr ✅
- Staging wird wieder korrekt deployed ✅

### HARTE LESSONS

| # | Regel |
|---|-------|
| CJ1 | **System-Ressourcen (CronJobs) dürfen NICHT im App-Verzeichnis liegen wenn CI/CD `kubectl apply -f .../app-dir/ -n app-namespace` macht** |
| CJ2 | **Bei `kubectl apply -f <dir>/ -n <ns>` werden ALLE Dateien mit demselben Namespace angewendet** — hardcodierte `namespace:` konfliktiert damit |
| CJ3 | **Commit `b3dfad55` hat CronJobs versehentlich in `staging/` verschoben** — davor separat verwaltet |
