# BAUPLAN — Docker-Compose + k3s Staging (2026-07-14)

## Status Docker: ✅ ABGESCHLOSSEN — 16/16 Services OK + 7/7 n8n Workflows ACTIVE + LiveKit Pipeline funktional

## Status k3s: ✅ ABGESCHLOSSEN — 16/16 Pods Running + Pipeline funktional + TLS aktiv + 7/7 n8n Workflows ACTIVE
⚠️ ACHTUNG: "ACTIVE" ≠ funktional. 5/7 n8n-Workflows haben broken `.tn` fromEmail (nur `user-invited` + `meeting-created` senden E-Mail, Phase 172). LiveKit Browser-Signal war bis Phase 173 broken (Ingress/NetworkPolicy).

## Was gelöscht wurde
| Was | Status |
|-----|--------|
| k3s Namespace `meeting-automation-staging` | ✅ gelöscht |
| Eigene Docker Images (v163, v168) | ✅ gelöscht |
| Docker Build Cache | ✅ 1.9GB aufgeräumt |
| openhive + alert-adapter | ✅ entfernt (kein Code) |

## Services (docker-compose.yml)

## Subscription Plans — Feature Matrix (Code-basiert)

| Feature | GRATUIT | PRO | ENTREPRISE |
|---------|---------|-----|------------|
| **Transcription Minutes/Monat** | 120 Min | 1800 Min (30h) | 3600 Min (60h) |
| **Preis** | 0€ | 99€ | 499€ |
| **API Calls/Min** | 30 | 120 | 600 |
| **Recordings/Tag** | 5 | 50 | unbegrenzt (-1) |
| **Transcriptions/Monat** | 10 | 200 | unbegrenzt (-1) |
| **Storage** | 1 GB | 10 GB | 50 GB |
| **Sentinel LLM (PV)** | ❌ Fallback (Text-Truncation) | ✅ Qwen-1.5B LLM | ✅ Qwen-1.5B LLM |
| **Celery Queue** | `transcription_gratuit` (3Gi) | `transcription_pro` (3Gi) | `transcription_pro` (3Gi) |
| **Backups** | ❌ deaktiviert | ✅ daily, 30d Retention | ✅ daily, 90d Retention |

### Was PRO von GRATUIT unterscheidet
1. **Sentinel LLM** — LLM-basierte PV-Generierung statt Text-Truncation (bessere Protokolle)
2. **15× mehr Transcription Minutes** (1800 vs 120)
3. **10× mehr Storage** (10GB vs 1GB)
4. **4× mehr Recordings/Tag** (50 vs 5)
5. **20× mehr Transcriptions/Monat** (200 vs 10)
6. **Daily Backups mit 30d Retention**

### Quellen im Code
- `backend/app/models/client.py:17-20` — SubscriptionPlan Enum
- `backend/app/services/rate_limiter.py:13-15` — API/Recording/Transcription Limits
- `backend/app/services/storage_quota.py:9-11` — Storage Quotas
- `backend/app/services/billing_service.py:17-19` — Minutes + Pricing
- `backend/app/tasks/transcription_tasks.py:329-360` — Sentinel LLM vs Fallback
- `backend/app/tasks/celery_app.py:62-80` — Queue-Routing

## Services (docker-compose.yml)

| # | Service | Port (extern) | Status |
|---|---------|--------------|--------|
| 1 | postgres | 5433 | ✅ healthy |
| 2 | redis | 6379 | ✅ healthy |
| 3 | rabbitmq | 5672, 15673 | ✅ healthy |
| 4 | minio | 9002, 9003 | ✅ healthy |
| 5 | n8n | 5678 | ✅ HTTP 200 |
| 6 | onlyoffice | 8082 | ✅ Running |
| 7 | backend | 8000 | ✅ healthy |
| 8 | celery-worker | — | ✅ Running |
| 9 | celery-beat | — | ✅ Running |
| 10 | frontend | 3000 | ✅ HTTP 200 |
| 11 | livekit-server | 7880 (host) | ✅ healthy |
| 12 | livekit-egress | 7000 (host) | ✅ healthy |
| 13 | livekit-redis | 6380 | ✅ healthy |
| 14 | prometheus | 9091 | ✅ HTTP 302 |
| 15 | grafana | 3004 | ✅ HTTP 302 |
| 16 | loki | 3101 | ✅ Running |

## Aufbau-Schritte

### Schritt 1: Cleanup
- [x] k3s Namespace löschen
- [x] Eigene Docker Images löschen
- [x] Build Cache aufräumen

### Schritt 2: Environment
- [x] .env existiert (1750 Bytes)

### Schritt 3: Build + Start
- [x] `docker compose build` (backend + frontend + celery + alert-adapter)
- [x] `docker compose up -d`
- [x] 16/16 Services Running

### Schritt 4: Initialisierung
- [x] PostgreSQL Migration (alembic upgrade head)
- [x] Users seeden (admin, dg, manager, user)
- [x] S3 Buckets erstellen (recordings, meeting-recordings-staging)

### Schritt 5: n8n Workflows importieren ✅
- [x] Owner Setup via `POST /rest/owner/setup` — admin@meeting.tn
- [x] 7 Workflows via n8n CLI importiert (alle 7 in DB)
- [x] SMTP Credential erstellt (ID: `4iyYNlqd77E6U4k3`, Mailtrap live.smtp.mailrap.io)
- [x] SMTP Credential in Workflow-Nodes updaten (korrekte ID)
- [~] fromEmail: nur `user-invited` (Phase 151/169) + `meeting-created` (Phase 172) korrigiert auf `noreply@meeting-automation.com`. **4 Workflows BLEIBEN auf `.tn` / OFFEN**: `transcription-completed` (`noreply@meeting-automation.tn`), `daily-reminders` (`escalations@meeting-automation.tn`), `meeting-status-changed` (`no-reply@meeting.tn`), `pv-validated` (`no-reply@meeting.tn`) — siehe Phase 172 OFFEN.
- [x] Workflows aktivieren: **7/7 ACTIVE** ✅

### Schritt 6: Verifikation
- [x] Frontend: http://localhost:3000 → 200
- [x] Backend: http://localhost:8000/health → healthy
- [x] n8n: http://localhost:5678 → 200
- [x] n8n: 7 Workflows importiert + aktiv ✅
- [x] LiveKit: ws://localhost:7880 → 200
- [x] MinIO: http://localhost:9003 → 200
- [x] RabbitMQ: http://localhost:15673 → 200
- [x] Grafana: http://localhost:3004 → 302
- [x] Prometheus: http://localhost:9091 → 302

## n8n Workflows (7 Stück)

| # | Workflow | Trigger | Erwartete ID (k3s) |
|---|----------|---------|-------------------|
| 1 | meeting-created | Webhook | `/webhook/meeting-created` (`webhookId=meeting-created-webhook-id`) — ⚠️ `uB0bPHLt0FNxsaBe` war legacy/stale |
| 2 | pv-validated | Webhook | `o9NXKZqiDnksQeO3` |
| 3 | transcription-completed | Webhook | `00tDUsvHjpnWD6oG` |
| 4 | meeting-status-changed | Webhook | `6jsJVqySI9VpnvoO` |
| 5 | daily-reminders | Cron (8:00 AM) | `GpER66AvYwapRNP4` |
| 6 | user-invited | Webhook | `CqkpcBkdkXlJtZbo` |
| 7 | audio-uploaded | Webhook | (nicht in AGENTS.md) |

> ⚠️ **"Erwartete ID (k3s)"-Spalte ist größtenteils stale/legacy**: Die Werte (`uB0bPHLt0FNxsaBe` usw.) sind alte Webhook-Node-IDs, NICHT die aktuellen k3s-Trigger-Pfade. Echter k3s-Webhook-Pfad = `POST /webhook/<path>` (z.B. meeting-created → `/webhook/meeting-created`, `webhookId=meeting-created-webhook-id`). Immer via `kubectl exec` in n8n-Pod + `SELECT nodes FROM workflow_entity` verifizieren, nicht der Tabelle vertrauen.

### n8n Konfiguration (Phase 151/152)
| Parameter | Wert |
|-----------|------|
| fromEmail | `noreply@meeting-automation.com` — nur user-invited + meeting-created; 4 weitere `.tn` (OFFEN, Phase 172) |
| SMTP Host | `smtp.mailtrap.io` (Port 587) |
| SMTP User | `api` |
| respondWith | `"text"` (NICHT `"success"` — existiert nicht in n8n 2.29) |
| DB | meeting_db (shared mit backend) |
| n8n liest aus | `workflow_history` (NICHT `workflow_entity`) |

### ⚠️ OFFEN: n8n Email-Versand
| # | Problem | Status |
|---|---------|--------|
| 1 | SMTP Host falsch: `live.smtp.mailrap.io` → `smtp.mailtrap.io` | ✅ gefixt |
| 2 | Credential-ID in workflow_history falsch (alte Versionen) | ✅ gefixt |
| 3 | Code Node: `$input.first().json.body.email` → `body \|\| json` | ✅ gefixt |
| 4 | Mailtrap "Too many failed login attempts" (nach vielen Fehlversuchen) | ⏳ WARTEN (5-10 Min) |
| 5 | **Noch nicht verifiziert ob E-Mail tatsächlich ankommt** | 🔴 OFFEN |

**Nächster Schritt:** Nach Mailtrap-Entsperrung Test mit `bkta3beispiel@googlemail.com` wiederholen.

### n8n HARTE LESSONS
| # | Regel |
|---|-------|
| 1 | **n8n liest Nodes aus `workflow_history`** — DB-Updates müssen in BEIDE Tabellen |
| 2 | **`respondWith: "success"` existiert nicht** — gültig: `"text"`, `"noData"`, `"firstEntryItemJson"` |
| 3 | **Workflow JSON Files im Repo sind OUTDATED** — enthalten noch `no-reply@meeting.tn` |
| 4 | **fromEmail muss `noreply@meeting-automation.com` sein** — nicht `*.tn` |
| 5 | **SMTP Host ist `smtp.mailtrap.io`** — NICHT `live.smtp.mailrap.io` (NXDOMAIN) |
| 6 | **n8n 2.29 braucht CLI `update:workflow --active=true`** — REST API PATCH aktiviert NICHT |
| 7 | **Credential-Daten sind verschlüsselt in der DB** — nur über REST API änderbar, nicht SQL |

## HARTE LESSONS (Gesamt)

| # | Regel | Aktion |
|---|-------|--------|
| N1 | **`DEBUG=true` MUSS in .env stehen** | Ohne DEBUG=true hat Cookie `Secure=True` → Browser schickt Cookie nicht über HTTP → "Not authenticated". Für docker-compose lokal MUSS `DEBUG=true` in .env stehen. Nach Änderung: `docker compose up -d --force-recreate backend` |
| N2 | **`LIVEKIT_PUBLIC_URL` MUSS Server-IP enthalten** | `ws://localhost:7880` funktioniert NUR wenn Browser auf dem Server läuft. Für externen Zugriff: `ws://158.180.18.110:7880`. Backend leitet `serverUrl` an Frontend weiter — Browser braucht die erreichbare IP. |
| N3 | **livekit-egress braucht `localhost` statt DNS** | `network_mode: host` kann Docker DNS nicht auflösen → Egress Config: `redis: localhost:6380`, `s3.endpoint: http://localhost:9002`. Nichts in `.env` überschreiben — Config-Datei (`livekit-egress.yaml`) ist die Quelle. |
| N4 | **Port-Konflikte prüfen VOR `docker compose up`** | `ss -tlnp` für alle geplanten Ports |
| N5 | **openhive hatte leeres Volume** | Nicht benutzt → entfernt aus docker-compose.yml |
| N6 | **LiveKit API Key/Secret MUSS übereinstimmen** | `livekit-host.yaml` Key/Secret MUSS identisch mit `.env` `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET` sein. Sonst: Token-Generierung schlägt fehl → "Not authenticated" im Frontend. |
| N7 | **LiveKit Egress braucht `--force-recreate` nach .env-Änderung** | `docker compose restart` übernimmt KEINE neuen Env-Vars. Nach `.env`-Änderung: `docker compose up -d --force-recreate livekit-egress` für neue API Key/Secret. Ohne das: Egress nutzt alte Keys → "recording service unavailable". |
| N8 | **HARTKODIERUNG VERBOTEN** | Keine IPs in `.env` oder Code hardcodieren. Docker-Compose Service-Namen oder `host.docker.internal` (bei host networking) nutzen. Config-Dateien (Deployment-spezifisch) sind erlaubt, aber nur `localhost` — kein `127.0.0.1` |
| N9 | **`LIVEKIT_EGRESS_S3_ENDPOINT` MUSS in `.env` stehen** | Der Backend-Code sendet `settings.LIVEKIT_EGRESS_S3_ENDPOINT` an die Egress-API. Ohne das: Egress bekommt keinen S3-Endpoint → `http://minio:9000` (Docker-Service-Name, nicht auflösbar bei host networking). Config-Datei wird NICHT genutzt wenn das Backend S3-Daten im Request sendet. |
| N10 | **Backend → LiveKit: `host.docker.internal` statt `localhost`** | `LIVEKIT_URL=ws://localhost:7880` funktioniert NICHT vom Backend-Container (bridge network) aus — HTTP 000. Nur `host.docker.internal:7880` erreicht den LiveKit Server (host network). Docker-Compose braucht `extra_hosts: - "host.docker.internal:host-gateway"` im backend-Service. |
| N11 | **Egress Config: `127.0.0.1` → `localhost`** | `127.0.0.1` und `localhost` sind NICHT identisch. Config-Dateien müssen `localhost` nutzen — nicht `127.0.0.1`. |
| N12 | **Celery Worker braucht ALLE Queues aus celery_app.py** | `celery_app.py` definiert 3 Queues: `transcription`, `transcription_gratuit`, `transcription_pro`. `get_transcription_queue()` routed GRATUIT→`transcription_gratuit`, PRO→`transcription_pro`. Worker `--queues` muss ALLE Queues enthalten: `transcription,transcription_gratuit,transcription_pro,email,maintenance`. Ohne das: Messages stecken in Queue mit 0 Consumers. |

## Zugriff (Docker)
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| n8n | http://localhost:5678 |
| LiveKit | ws://localhost:7880 |
| OnlyOffice | http://localhost:8082 |
| MinIO Console | http://localhost:9003 |
| RabbitMQ Mgmt | http://localhost:15673 |
| Grafana | http://localhost:3004 |
| Prometheus | http://localhost:9091 |
| Login | admin@meeting.tn / Password123! |

---

# BAUPLAN — k3s Staging Deployment

## Was gemacht wurde

### Schritt 1: Docker-Compose stoppen
- `docker compose down` — alle Container gestoppt und entfernt
- Grund: Port-Konflikte (LiveKit hostNetwork 7880/7000)

### Schritt 2b: Consent-Bug-Fix (Phase 163 NACHTRAG, 2026-07-17)
- **3 Bugs gefixt** (Details `.loop.md` Phase 163 NACHTRAG): (1) Enum Name=Value `C1_AUDIO="C1_AUDIO"` in `schemas/consent.py` + `models/consent.py`; (2) `all_required_granted` str/Enum-robust in `consent.py`; (3) Recording-Gate filtert `user_id` in `recording_service.py`. Neue Migration `c1d2e3f4a5b6` typet `consent_logs.consent_type` auf Native-ENUM.
- **Backend-Image rebuild** (OHNE `SKIP_SENTINEL`, C7): `docker build --build-arg SKIP_SENTINEL=false -t batnini/meeting-automation-backend:latest .` (~118s, Cache da). Sentinel LLM inkludiert.
- **Import**: `docker save ... -o /home/opc/backend-latest.tar` (NICHT /tmp, C10) → `k3s ctr images import` → verify.
- **Rollout**: `kubectl rollout restart deployment/backend deployment/celery-worker-staging deployment/celery-worker-pro-staging deployment/celery-beat-staging`.
- **Verifikation**: `POST /auth/register` mit `consents` → HTTP 201; `consent_logs.consent_type` = Native-ENUM `consent_type`; Logs `[C1_AUDIO, C2_VOICE, C3_SHARING, C4_STORAGE]`. Neukunde aus Landingpage-Login-Flow kann jetzt consented abonnieren + Recording nutzen.

### Schritt 2: Docker Images bauen + in k3s importieren
- `docker.io/batnini/meeting-automation-backend:latest` (= **`3394acaef...`** lokal / k3s arm64 `c2d0a677...`, 1.8GB) — enthält Consent-Fix (main.py:335) + llama-cpp-python 0.3.34 + Qwen2.5-1.5B GGUF + ONNX. Gebaut OHNE `SKIP_SENTINEL` (Phase 163, 2026-07-17).
- `docker.io/batnini/meeting-automation-frontend:latest` (37MB) — React SPA + Nginx. Enthält Phase-163 PrivacyPage (`/privacy`) + TermsPage Consent-Sektion (`/terms`) + Footer-RouterLinks (EN/FR/AR, INPDP Loi 2004-63 Art.47 referenziert). Gebaut 2026-07-17.
- Import via: `docker save | k3s ctr images import`
- **Image-Tags für Deployment-YAMLs (Stand 2026-07-17):**
  - `backend-deployment.yaml:23` (main) + `:42` (initContainer alembic-migrate) → `batnini/meeting-automation-backend:latest`
  - `celery-worker-deployment.yaml:22` → `batnini/meeting-automation-backend:latest`
  - `celery-worker-pro-deployment.yaml:22` → `batnini/meeting-automation-backend:latest`
  - `celery-beat-deployment.yaml:20` → `batnini/meeting-automation-backend:latest`
  - `frontend-deployment.yaml` → `batnini/meeting-automation-frontend:latest`
  - ⚠️ `consent-fix3-20260716222317` wurde GELÖSCHT (Phase 163) — darf in keinen YAMLs mehr stehen.

### Schritt 3: setup-kubernetes-staging.sh gefixt
| # | Was | Grund |
|---|-----|-------|
| 1 | Context-Wechsel: `staging-cluster` → `default` | `staging-cluster` zeigte auf alten Kind-Cluster (Port 44469), nicht k3s (Port 6443) |
| 2 | `celery-worker-pro-deployment.yaml` zur Schleife hinzugefügt | Phase 159 3-Tier-Architektur: GRATUIT + PRO Workers |
| 3 | `kubeconfig-staging.txt` umbenannt → `.bak-kind` | Alte Kind-Config überschrieb KUBECONFIG |

### Schritt 4: Image-Pull-Fehler gefixt
| # | Was | Grund |
|---|-----|-------|
| 1 | `backend-deployment.yaml`: `imagePullPolicy: Always` → `IfNotPresent` | k3s kann nicht von docker.io/batnini/ pullen — Images sind lokal importiert |
| 2 | `frontend-deployment.yaml`: `imagePullPolicy: Always` → `IfNotPresent` | Gleicher Grund |
| 3 | `n8n-secrets`: `N8N_API_KEY` hinzugefügt | Secret-Key fehlte → `CreateContainerConfigError` |

### Schritt 5: Deployment ausgeführt
- `bash setup-kubernetes-staging.sh` — Schritt 1-6 durchgelaufen
- Namespace: `meeting-automation-staging`
- Storage: `local-path` (Single-Node)
- CNPG: 1 Instance

### Aktueller Status: 16/16 Pods Running
| # | Pod | Status |
|---|-----|--------|
| 1 | backend ×2 | ✅ Running |
| 2 | celery-worker GRATUIT ×2 | ✅ Running |
| 3 | celery-worker PRO ×2 | ✅ Running |
| 4 | celery-beat | ✅ Running |
| 5 | frontend | ✅ Running | (Phase-163 Privacy/Terms Pages, `/privacy` + `/terms` Routes, Footer RouterLink) |
| 6 | livekit-server | ✅ Running (hostNetwork) |
| 7 | livekit-egress | ✅ Running (hostNetwork) |
| 8 | meeting-db (CNPG) | ✅ Running |
| 9 | redis | ✅ Running |
| 10 | rabbitmq | ✅ Running |
| 11 | minio | ✅ Running |
| 12 | n8n | ✅ Running |
| 13 | onlyoffice | ✅ Running |

### Hardware-Anforderung (korrigiert, Stand 2026-07-15 / Phase 174)

**Node (Single-Node k3s, OCI VM):**
| Parameter | Wert |
|-----------|------|
| vCPU | 4 OCPUs (ARM64, Oracle Linux 9.7) |
| RAM | **24 GB** |
| Arch | aarch64 (ARM64) — Images müssen ARM64-kompatibel sein (k3s ctr import) |
| Storage | lokal (`local-path`), Single-Node (kein Longhorn — braucht ≥2 Nodes) |

**Celery 3-Tier Worker — KORRIGIERT (Phase 174):**
| Tier | Replicas | Memory/Replica | Queue | Zweck |
|------|----------|----------------|-------|-------|
| GRATUIT | 2 | **3Gi** (requests 1500Mi) | `transcription_gratuit` | Fallback (kein LLM) — verarbeitet ABER identische Audio/Gladia/Mistral-Last wie PRO |
| PRO/ENT | 2 | 3Gi (requests 1500Mi) | `transcription_pro` | Sentinel LLM (Qwen2.5-1.5B) |
| Beat | 1 | 1Gi | `maintenance`,`email` | Scheduled Tasks (daily reminders, cleanup) |

> ⚠️ **KORREKTUR zu Phase 159**: Phase 159 setzte GRATUIT auf `2× 1Gi`. Das war zu wenig — der GRATUIT-Worker wurde beim Verarbeiten von Audio + Gladia **OOMKilled (Exit 137, Phase 174)** → Crash-Loop → Pipeline hing. Richtig: GRATUIT braucht **GENAUSO 3Gi** wie PRO (beide verarbeiten dieselbe Last, nur das LLM-Summary unterscheidet sich). Phase 159 Tabelle "Gesamt 10Gi" ist daher **veraltet**; korrekt für die 3 Worker-Tiers allein: 2+6+6+1 = **15Gi** (Limits). Diese Korrektur ist in `celery-worker-deployment.yaml` (Phase 174) bereits applied.

**Sentinel LLM (PRO/ENT) pro Pod** (Phase 159 Ressourcen-Berechnung, gemessen):
- Modell `Qwen2.5-1.5B` GGUF `Q4_K_M`: **1.04 GB Disk**, ~1.3 GB RAM (Gewichte 800MB + KV-Cache 448MB + Buffers 100MB) + ~200MB Python-Overhead ≈ **~1.5 GB RAM/Pod**

**Memory pro Tenant (Cloud) — Plan-Referenz** (Phase 78):
| Plan | Idle RAM | Peak RAM | Container-Limit |
|------|----------|----------|-----------------|
| GRATUIT | 4×300 MB = 1.2 GB | ~2 GB | 4 Gi |
| PRO/ENTREPRISE | 4.2 GB | ~5 GB | 8 Gi |

**Hinweis Kapazität:** Summe der Memory-Limits der 3 Worker-Tiers (~15Gi) + Backend/LiveKit/DB/n8n etc. liegt nahe an / über den 24Gi des Nodes. K8s schedulct auf *Requests* (GRATUIT 1500Mi×2, PRO 1500Mi×2, Backend 512Mi×2, …), nicht auf Limits — daher laufen alle 16 Pods trotzdem. Bei mehr gleichzeitigen Recordings ist das Node-Limit (24Gi) der Flaschenhals → HPA (`celery-worker-hpa.yaml`, 1–4 Replicas) bzw. Node-Resize nötig.

## Ausstehende Schritte (7-12)
| # | Schritt | Status |
|---|---------|--------|
| 7 | Alembic Migration (`alembic upgrade head`) | ✅ head: s6t7u8v9w0x1 (Consent, Phase 163) |
| 8 | Users seeden + S3 Buckets | ✅ 4 Users + 3 Buckets (recordings, meeting-recordings-staging, velero-backups) |
| 9 | Backup-Systeme (CNPG + Velero) | ✅ Initial Backup laufend + ScheduledBackup (2:00 AM) |
| 10 | Pod-Status + Login-Test | ✅ 16/16 Running, admin@meeting.tn Login OK |
| 11 | Smoke Tests (port-forward + health) | ✅ Backend healthy, Frontend HTTP 200, Auth OK |
| 12 | Backup-Status prüfen | ✅ CNPG Backup laufend, ScheduledBackup registriert |
| 13 | n8n Owner Setup + Workflows importieren | ✅ admin@meeting.tn + 7/7 Workflows ACTIVE |
| 14 | Pipeline Test (Meeting → LiveKit Token) | ✅ Meeting erstellt, Token generiert, serverUrl=wss://staging.meeting-automation.com |
| 15 | TLS (nginx-ingress + cert-manager + Let's Encrypt) | ✅ HTTP 308→HTTPS, Certificate READY, Frontend 200 |
| 16 | n8n Webhook Fix (Encryption Key + activeVersionId) | ✅ 7/7 Webhooks registriert, user-invited getestet |

## TLS Setup (Phase 167)
| # | Schritt | Status |
|---|---------|--------|
| 1 | nginx-ingress Controller installieren | ✅ hostPort 80/443 via hostNetwork |
| 2 | cert-manager installieren | ✅ 3/3 Pods Running |
| 3 | Let's Encrypt ClusterIssuer (HTTP-01) | ✅ `letsencrypt-prod` |
| 4 | Ingress Frontend + Backend | ✅ `staging.meeting-automation.com` |
| 5 | Ingress LiveKit WebSocket `/rtc` + `/twirp` | ✅ WebSocket-Timeouts 86400s |
| 6 | TLS Secret `staging-tls` | ✅ Let's Encrypt Zertifikat ausgestellt |
| 7 | firewalld: 80/tcp + 443/tcp | ✅ bereits geöffnet |

### TLS Verifikation
- `http://staging.meeting-automation.com` → 308 Redirect → HTTPS ✅
- `https://staging.meeting-automation.com` → HTTP 200 ✅
- Certificate: READY=True, Secret `staging-tls` ✅
- LiveKit Token: `serverUrl=wss://staging.meeting-automation.com` ✅

### n8n externer Zugriff
- **NodePort 31678**: `http://158.180.18.110:31678` → n8n Login (wie auf 09.07)
- **Service**: `n8n-staging` (NodePort 5678→31678) — **in Phase 170 re-aktiviert** (war zwischenzeitlich auf `ClusterIP` → Port war UNERREICHBAR, Doku war falsch!)
- **NetworkPolicy**: `n8n-nodeport-policy` existiert (POD-Selector `app=n8n-staging`), wird aber von flannel **NICHT erzwungen** (k3s Default-CNI = flannel, keine NP-Enforcement) → rein dekorativ
- **firewalld**: `31678/tcp` in `public`-Zone (Interface `enp0s6`) offen
- ⚠️ **Sicherheitsrisiko**: Zugriff ist **unverschlüsselt (HTTP, kein TLS)** → n8n Login + Credential-Inhalte im Klartext im Internet. Siehe Gefahr G2 in Phase 170. Empfohlene saubere Lösung: Subdomain-Ingress `n8n.staging.meeting-automation.com` mit TLS (Phase 170).

### n8n Webhook Fix (Phase 168)
- **Problem**: Alle n8n Webhooks gaben 404 — Workflows waren nicht "published"
- **Root Cause 1**: `N8N_ENCRYPTION_KEY` fehlte in n8n-secrets → Pod generiert bei jedem Restart neuen Key → Workflows unlesbar
- **Root Cause 2**: `activeVersionId=NULL` für alle 7 Workflows → n8n v2.30.4 erkennt sie nicht als "published" → `webhook_entity` leer → 404
- **Fix 1**: `N8N_ENCRYPTION_KEY` zum n8n-secrets hinzugefügt (openssl rand -hex 32)
- **Fix 2**: Alte Workflows aus DB gelöscht, neu importiert via CLI, `activeVersionId = versionId` via DB-Update gesetzt
- **Verifikation**: `{"message":"Workflow was started"}` + 1 Execution ✅

## k3s Zugriff
| Service | URL/Zugriff |
|---------|------------|
| Frontend | `https://staging.meeting-automation.com` |
| Backend | `https://staging.meeting-automation.com/api` |
| n8n | `http://158.180.18.110:31678` |
| LiveKit | ws://158.180.18.110:7880 (hostNetwork) |
| Login | admin@meeting.tn / Password123! |

## k3s HARTE LESSONS
| # | Regel |
|---|-------|
| K1 | **`staging-cluster` Context zeigt auf alten Kind-Cluster** — k3s läuft unter `default` Context (Port 6443). `kubeconfig-staging.txt` umbenennen oder Script auf `default` umstellen. |
| K2 | **`imagePullPolicy: Always` + lokale Images = ImagePullBackOff** — Bei lokal importierten Images MUSS `imagePullPolicy: IfNotPresent` gesetzt sein. Sonst versucht k3s von Registry zu pullen. |
| K3 | **Docker-Compose muss gestoppt werden** — LiveKit `hostNetwork: true` beansprucht Ports 7880/7000 die auch k3s LiveKit braucht. |
| K4 | **Image-Tags müssen mit Deployment-YAMLs übereinstimmen** — `k3s ctr images tag` für Aliasse wenn YAML `batnini/` aber Image `library/` heißt. |
| K5 | **n8n Secret braucht N8N_API_KEY** — `n8n-deployment.yaml` referenziert `N8N_API_KEY` aus `n8n-secrets`. Fehlender Key → `CreateContainerConfigError`. |
| K6 | **n8n Workflows via DB aktivieren** — CLI `update:workflow` braucht volle N8n-Env-Vars die im Container fehlen. DB-Update `UPDATE workflow_entity SET active=true` + n8n-Restart funktioniert. |
| K7 | **Celery Worker CrashLoopBackOff nach langem ImagePullBackOff** — Nach 27min ImagePullBackOff (v20260709182130 nicht gefunden), Pod in CrashLoopBackOff. Lösung: Pods löschen für frischen Restart. |
| K8 | **FastAPI 307 Redirect bei trailing slash** — `/api/v1/meetings` → 307 Redirect → `/api/v1/meetings/`. Curl braucht `-L` Flag oder trailing slash in URL. |
| K9 | **LiveKit Token Key ist `participantToken`** — nicht `token`. Response: `{serverUrl, roomName, participantName, participantToken}`. |
| K10 | **nginx-ingress baremetal braucht hostNetwork + hostPort** — Ohne hostPort 80/443 ist Controller nicht extern erreichbar. `kubectl patch deployment` für hostPort-Patch. |
| K11 | **Alte ReplicaSets blockieren neue Deploys** — 20 Tage alte Pods in Error-State verhindern Scheduling. Lösung: Namespace komplett löschen (Finalizer entfernen via `kubectl replace --raw`) + Fresh Install. |
| K12 | **cert-manager braucht admission-create Job ZUERST** — Controller Pod kann Secret nicht mounten wenn Job noch nicht gelaufen. Admission-Jobs müssen vor Controller-Pod laufen. |
| K13 | **k3s kann nicht von registry.k8s.io pullen** — Images müssen via Docker pullen → `k3s ctr images import` für lokale Nutzung. |
| K14 | **Let's Encrypt HTTP-01 braucht Port 80 von außen** — firewalld 80/tcp muss offen sein (Phase 148). ACME Challenge kommt von Let's Encrypt Server. |
| K15 | **n8n braucht N8N_ENCRYPTION_KEY in Secret** — Ohne Key generiert n8n bei jedem Restart neuen Key → importierte Workflows unlesbar → "0 draft workflows, 0 published". Key MUSS stabil sein in n8n-secrets. |
| K16 | **n8n v2.30.4 braucht `activeVersionId = versionId`** — `active=True` reicht NICHT für Webhook-Registrierung. Workflow muss `activeVersionId` gesetzt haben (DB-Update) + n8n-Restart. Sonst: `webhook_entity` leer → 404 auf allen Webhooks. |
| K17 | **N8N_ENCRYPTION_KEY MUSS ins Deployment-Env** — Phase 168 hat den Key nur in `n8n-secrets` gepackt, aber NICHT ins `n8n-deployment.yaml` als `env.secretKeyRef` referenziert. Deshalb generiert n8n weiterhin ephemeralen Auto-Key in `/root/.n8n/config` (Container-FS, nicht PVC). Fix: `env` Block im Deployment um `N8N_ENCRYPTION_KEY` aus `n8n-secrets` erweitern. |
| K18 | **Credential-Verschlüsselung ist OpenSSL AES-256-CBC** (`Salted__` + Salt + Ciphertext, base64 in `credentials_entity.data`). n8n entschlüsselt nur mit dem Key, der BEIM Anlegen genutzt wurde. Key-Wechsel → altes Credential unlesbar → DELETE + neu CREATE nötig. |
| K19 | **REST API PATCH ignoriert Credential-ID-Änderungen in Nodes** — `PATCH /rest/workflows/{id}` mit geänderter `credentials[].id` im Node → Response zeigt alte ID, DB unverändert. Credential-Referenzen in Workflow-Nodes NUR via DB `UPDATE ... SET nodes = replace(nodes::text, 'ALT', 'NEU')` änderbar (BEIDE Tabellen: `workflow_entity` + `workflow_history`). |

---

# Phase 169: n8n SMTP Email-Pipeline Reparatur (2026-07-15)

## Status: ✅ ABGESCHLOSSEN (2026-07-15) — E-Mail-Versand verifiziert via Execution 10 (status: success)

## Problem (bewiesen via Tests, nicht geraten)
| # | Problem | Beweis |
|---|---------|--------|
| 1 | `N8N_ENCRYPTION_KEY` fehlt im Deployment-Env → n8n auto-generiert ephemeralen Key `uk1uwjLV62pM6xFFmXaM8xy/914FRYC+` in `/root/.n8n/config` (Container-FS, geht bei Restart verloren) | `kubectl exec cat /root/.n8n/config`; Deployment-YAML Zeile 48-52 hat nur `N8N_API_KEY` |
| 2 | Secret `n8n-secrets` hat `N8N_ENCRYPTION_KEY=b6cb1ac9...` (Phase 168), aber Deployment referenziert ihn NICHT | `kubectl get secret n8n-secrets -o json` + Deployment-YAML check |
| 3 | SMTP Credential `VJcH9L41G0TRyOok` verschlüsselt mit auto-Key `uk1uwjL...` → nach Key-Wechsel (Secret-Key `b6cb1ac...`) unlesbar | OpenSSL `Salted__` Format in `credentials_entity.data` |
| 4 | Backend `SMTP_HOST=bulk.smtp.mailrap.io` (NXDOMAIN) + `SMTP_PASSWORD` fehlt komplett | `kubectl get configmap backend-config`; `kubectl get secret backend-secrets-staging` |
| 5 | `smtp.mailtrap.io` erreichbar (TLS OK, 3.209.246.195), `bulk.smtp.mailrap.io` NXDOMAIN | `openssl s_client -connect smtp.mailtrap.io:587` |
| 6 | `activeVersionId` already gesetzt für alle 7 Workflows (`has_active_version=t`) → Webhooks registrieren OK | DB-Check `workflow_entity` |
| 7 | n8n liest alle 8 Workflows via REST API → Workflows sind PLAINTEXT (nur Credentials verschlüsselt) | REST API GET /rest/workflows |

## Plan
| # | Schritt | Aktion | ISO 27001 |
|---|---------|--------|-----------|
| 1 | `N8N_ENCRYPTION_KEY` ins Deployment | `infrastructure/kubernetes/staging/n8n-deployment.yaml` edit: `env` Block um `secretKeyRef: n8n-secrets/N8N_ENCRYPTION_KEY` erweitern → `kubectl apply -f` | A.8.24 konform (Secret-Ref, nicht Plaintext) |
| 2 | Pod-Restart + NEU Login | `kubectl rollout restart deployment/n8n-staging` → warten bis Ready → Cookie neu holen | — |
| 3 | Altes Credential löschen | `DELETE /rest/credentials/VJcH9L41G0TRyOok` | — |
| 4 | Neues Credential erstellen | `POST /rest/credentials` mit `live.smtp.mailtrap.io:587` (**Sending-Endpoint!** `api`-User wird auf `smtp.mailtrap.io` (Testing) mit `535 Invalid credentials` abgewiesen), user `api`, pwd `4e2fbbb5ef37900bd76094b79a0dbb82`, sender `noreply@meeting-automation.com` | A.8.24 (in K8s Secret verschlüsselt) |
| 5 | Workflow-Nodes updaten | DB `UPDATE workflow_entity SET nodes=replace(..., 'VJcH9L41G0TRyOok', 'nTNtib8Ge4k4Wjv9')::json` + gleiches für `workflow_history` (6 Rows je Tabelle) | — |
| 6 | Backend SMTP fix | ConfigMap `backend-config`: `SMTP_HOST=live.smtp.mailtrap.io`; Secret `backend-secrets-staging`: `SMTP_PASSWORD` hinzufügen; `kubectl rollout restart deployment/backend` | A.8.24 |
| 7 | Verifikation | `POST /webhook/user-invited` mit `{email, full_name, activation_link}` → Execution 10 `status: success`, kein EAUTH-Fehler | — |

## Ergebnis (verifiziert)
- **Neue Credential-ID**: `nTNtib8Ge4k4Wjv9` (`live.smtp.mailtrap.io:587`, `secure:false`, user `api`, sender `noreply@meeting-automation.com`)
- **Host-Korrektur (kritisch)**: `api`-User funktioniert NUR auf Mailtraps **Sending**-Endpoint `live.smtp.mailtrap.io` (bzw. `bulk.smtp.mailtrap.io`). `smtp.mailtrap.io` ist der **Testing**-Inbox-Endpoint und lehnt `api` mit `535 5.7.0 Invalid credentials` ab. Direkter `smtplib`-Test bestätigt: `live.smtp.mailtrap.io:587` → `LOGIN OK`.
- **Execution 10** (Workflow 6 `User Invited Webhook`, getriggert via `POST /webhook/user-invited`): `status: success`, Send-Email-Node lief ohne Fehler → E-Mail an `batniniabdelkader@yahoo.com` versendet.
- **Backend**: ConfigMap `SMTP_HOST=live.smtp.mailtrap.io` + `SMTP_PASSWORD` im Secret, Restart erfolgreich.
- **Test-Artefakte aufgeräumt**: `bkx9FeNn2GB9FOMK` (TEST_DELETE_ME), `ceRaz2f14bJ8n0IP` (SMTP Test Minimal), `p9UBz1CljqDWduCn` (SMTP Test Webhook) gelöscht (vorher archivieren nötig: `POST /rest/workflows/{id}/archive`).
- **ISO 27001**: A.8.24 konform — Key via `secretKeyRef`, Credential in K8s-Secret verschlüsselt, kein Plaintext.

## Fallbacks (bei Fehlschlag)
| FB | Trigger | Aktion |
|----|---------|--------|
| F1 | REST DELETE Schritt 3 fehlgeschlagen (Credential unlesbar nach Key-Wechsel) | DB direkt: `DELETE FROM credentials_entity WHERE id='VJcH9L41G0TRyOok'; DELETE FROM shared_credentials WHERE "credentialsId"='VJcH9L41G0TRyOok';` |
| F2 | n8n liest Workflows nach Restart nicht (K15-Szenario) | Workflows via REST API exportieren (`GET /rest/workflows/{id}`) → nach Neustart mit neuem Key via `POST /rest/workflows` re-importieren → `activeVersionId=versionId` setzen |
| F3 | DB REPLACE Schritt 5 nicht wirksam (n8n cached nodes) | `kubectl rollout restart deployment/n8n-staging` (zwingt n8n Neuladen aus DB) |
| F4 | Backend SMTP_PASSWORD im Secret nicht greifend | Backend Deployment `env` direkt mit `SMTP_PASSWORD` aus Secret via `secretKeyRef` ergänzen |

## Wichtig: Reihenfolge
```
Schritt 1 (Key ins Deployment) → Schritt 2 (Restart + NEU Login)
  → Schritt 3 (Altes Credential löschen) → Schritt 4 (Neues anlegen)
  → Schritt 5 (DB REPLACE beide Tabellen) → Schritt 6 (Backend) → Schritt 7 (Test)
```

---

# Phase 170: n8n Web-Zugriff via NodePort 31678 re-aktiviert (2026-07-15)

## Status: ✅ ABGESCHLOSSEN — `http://158.180.18.110:31678` wieder erreichbar

## Ausgangslage / Gefahr (dokumentiert weil kritisch)
| # | Gefahr | Beweis / Auswirkung |
|---|--------|---------------------|
| **G1** | **Doku ≠ Cluster-Zustand (kritisch)** | BAUPLAN behauptete seit Phase 167/168 dauerhaft "NodePort 31678 erreichbar". Realität: Service `n8n-staging` war auf `ClusterIP` geändert → Port 31678 war **UNERREICHBAR**. Wer sich auf die Doku verließ, kam nicht an n8n ran. Service-Typ-Änderungen MÜSSEN dokumentiert werden. |
| **G2** | **Unverschlüsselter Public Exposure** | `http://158.180.18.110:31678` (kein TLS) überträgt n8n Login + Credential-Inhalte im Klartext ins Internet → Angriffsfläche für Credential-Theft / Brute-Force. |
| **G3** | **Broken `/n8n` Ingress-Route** | Ingress `meeting-staging` routet `/n8n` → `n8n-staging:5678`, liefert aber defekte UI: Assets laden von bare `/` statt `/n8n` (`/assets/index-*.js` → fällt auf Frontend durch) → wer sie nutzt, sieht kaputte Seite und denkt n8n sei down. |
| **G4** | **NodePort auf allen Nodes / Public IP** | NodePort horcht via kube-proxy auf 0.0.0.0 des Nodes; bei mehreren Nodes wäre der Port auf ALLEN Nodes offen. Single-Node hier, aber Prinzip beachten. |

## Lösung / Plan
| # | Variante | Aktion | Status |
|---|----------|--------|--------|
| **L1 (umgesetzt, kurzfristig)** | NodePort re-aktivieren | `kubectl patch service n8n-staging --type merge -p '{"spec":{"type":"NodePort","ports":[{"port":5678,"targetPort":5678,"nodePort":31678}]}}'` → Service `NodePort 5678:31678/TCP`. firewalld `public`-Zone hatte `31678/tcp` schon erlaubt (Reload nach Aktivierung). | ✅ |
| **L2 (empfohlen, mittelfristig)** | Saubere Subdomain-Ingress | Neue Ingress `n8n-staging` mit Host `n8n.staging.meeting-automation.com` → `n8n-staging:5678` + TLS (cert-manager `staging-tls`). Benötigt DNS A/Record `n8n.staging.meeting-automation.com` → `158.180.18.110` (Cloudflare). Danach Service zurück auf `ClusterIP` → kein offener Port. | ⏳ (DNS nötig) |
| **L3 (Alternative)** | `/n8n` Subpath korrekt | n8n Env ergänzen: `N8N_PATH=/n8n`, `N8N_PROTOCOL=https`, `N8N_EDITOR_BASE_URL=https://staging.meeting-automation.com/n8n`, `WEBHOOK_URL=https://staging.meeting-automation.com/n8n` → Restart. Dann funktioniert die vorhandene `/n8n`-Route ohne Asset-Bug. | ⏳ |

**Empfehlung**: L2 (Subdomain + TLS) — entfernt das G2-Risiko komplett und macht NodePort überflüssig. L1 nur als Interim bis L2/DNS steht.

## Pipeline-Beweis (verifiziert)
**SMTP E-Mail-Versand (Phase 169 Kern):**
- `POST /webhook/user-invited` mit `{email, full_name, activation_link}` → **Execution 10 `status: success`**, Send-Email-Node fehlerfrei → Mail an `batniniabdelkader@yahoo.com` versendet.
- Direkter `smtplib`-Test: `live.smtp.mailtrap.io:587` (Sending-Endpoint) + user `api` → **`LOGIN OK`**. `api`-User wird auf `smtp.mailtrap.io` (Testing) mit `535 Invalid credentials` abgewiesen → Host-Korrektur war entscheidend.
- Credential `nTNtib8Ge4k4Wjv9` (`live.smtp.mailtrap.io:587`, `secure:false`, user `api`) in 6 Workflows referenziert (DB-Check: 6 neu / 0 alt), Backend `SMTP_HOST=live.smtp.mailtrap.io` + `SMTP_PASSWORD` im Secret.

**Web-Zugriff (Phase 170):**
- `curl 127.0.0.1:31678/` → **HTTP 200** (Service→Pod→n8n Kette intakt, Assets von bare `/` = korrekt für Root-Path).
- Service `n8n-staging` = `NodePort 5678:31678/TCP`; firewalld `public` (Interface `enp0s6`) offen für `31678/tcp`.
- Öffentliche IP `158.180.18.110` ist OCI-NAT-IP (nicht lokal an NIC gebunden) → externer Browser erreicht den Port via NAT; lokales `curl` auf die Public-IP schlägt wegen Hairpin-NAT fehl (normal, kein Fehler).

## Fallbacks
| FB | Trigger | Aktion |
|----|---------|--------|
| F1 | NodePort nicht erreichbar (firewalld blockt) | `sudo firewall-cmd --add-port=31678/tcp --permanent && sudo firewall-cmd --reload` (Interface `enp0s6` ist in `public`-Zone) |
| F2 | Service wieder ClusterIP nach Deploy | `kubectl patch service n8n-staging --type merge -p '{"spec":{"type":"NodePort","ports":[{"port":5678,"targetPort":5678,"nodePort":31678}]}}'` |
| F3 | `/n8n` Ingress kaputt (G3) | L3 anwenden (N8N_PATH) ODER L2 (Subdomain) — `/n8n` vorher nicht nutzen |

## HARTE LESSON (neu)
- **K20 — Service-Typ-Änderungen MÜSSEN dokumentiert werden**: `ClusterIP`↔`NodePort` ist eine reale Erreichbarkeits-Änderung. BAUPLAN darf nicht "NodePort erreichbar" behaupten wenn das Service `ClusterIP` ist (G1). Immer `kubectl get svc` vor Dokumentations-Claim.
- **K21 — NodePort = unverschlüsselter Public Port**: `http://host:nodePort` ohne TLS. Für dauerhaften Zugriff Subdomain-Ingress mit TLS (L2) bevorzugen, NodePort nur interim.
- **K22 — n8n hinter Subpath braucht `N8N_PATH`**: Ohne `N8N_PATH=/n8n` lädt n8n Assets von `/` statt `/n8n` → defekte UI (G3). Root-Path (NodePort) hat dieses Problem nicht.
- **K23 — Neuer Worker-Tier MUSS in ALLE Server-NetworkPolicies**: Bei `default-deny-all` (Ingress) im Namespace reicht es nicht, den Deployment-YAML des neuen Tiers zu pflegen. Der Pod braucht zwingend `podSelector: app=<tier>` in den `From`-Listen von `rabbitmq-policy`, `redis-policy`, `postgres-policy`, `minio-policy`, `cnpg-policy` — sonst Connection-refused auf RabbitMQ → Crash-Loop. PRO-Tier (`celery-worker-pro-staging`) war in Phase 171 genau daran gescheitert.

---

# Phase 171: celery-worker-pro-staging Crash-Loop Reparatur (2026-07-15)

## Status: ✅ ABGESCHLOSSEN — PRO-Worker `1/1 Running`, 0 Restarts, `celery@... ready.`, gesamte k3s-Pipeline re-verifiziert

## Problem (bewiesen via Logs + NetworkPolicy-Inspektion)
| # | Symptom | Beweis |
|---|---------|--------|
| 1 | PRO-Pods crash-loopten (226 Restarts), GRATUIT-Pods 0 Restarts — bei IDENTISCHEM Startup-Command | `kubectl get pods` + Deployment-YAML-Vergleich |
| 2 | PRO-Pod-Log: endloses `bash: /dev/tcp/rabbitmq-staging/5672: Connection refused` → Pre-Check-Loop nie erfüllt → celery startet nie | `kubectl logs celery-worker-pro-staging-...` |
| 3 | Liveness-Probe `celery inspect ping` schlägt fehl (kein Worker) → Kubelet killt Container → Restart | Policy `default-deny-all` (Ingress) im Namespace aktiv |
| 4 | `rabbitmq-policy` (und redis/postgres/minio/cnpg) erlauben nur `app: celery-worker-staging` (GRATUIT), NICHT `app: celery-worker-pro-staging` | `kubectl describe networkpolicy rabbitmq-policy` → From: backend, celery-worker-staging, celery-beat-staging |

**Root Cause:** Namespace hat `default-deny-all` (Ingress). Die Server-Policies gewährten Ingress nur an GRATUIT (`celery-worker-staging`), nie an PRO (`celery-worker-pro-staging`). PRO-Pods wurden am RabbitMQ-Zugriff geblockt → Connection refused → Startup-Pre-Check loop → celery nie gestartet → Liveness-Fail → Crash-Loop. GRATUIT lief, weil er in den `From`-Listen stand.

## Plan / Fix
| # | Aktion | ISO 27001 |
|---|--------|-----------|
| 1 | `infrastructure/kubernetes/staging/network-policies.yaml`: `podSelector: {app: celery-worker-pro-staging}` zu `From`-Listen von `rabbitmq-policy`, `redis-policy`, `postgres-policy`, `minio-policy`, `cnpg-policy` hinzugefügt | A.8.24 (Ursache behoben, Policy NICHT gelöscht — „Löschen ist verboten") |
| 2 | `kubectl apply -f network-policies.yaml` → `postgres/redis/rabbitmq/minio/cnpg-policy configured` | — |
| 3 | `kubectl rollout restart deployment/celery-worker-pro-staging` → ReplicaSet `5b79458d64`, Rollout success | — |

**Hinweis:** Kein Command-Change nötig — PRO-Command ist identisch zu GRATUIT und korrekt. Der Pre-Check `/dev/tcp/rabbitmq-staging/5672` erfüllt sich selbst, sobald die NetworkPolicy den Zugriff erlaubt.

## Ergebnis (verifiziert)
- **PRO-Pods**: `1/1 Running`, **0 Restarts** (vorher 226). Log: `Connected to amqp://rabbit_user:**@rabbitmq-staging.meeting-automation-staging.svc.cluster.local:5672//` → `celery@celery-worker-pro-staging-5b79458d64-7wnkb ready.`
- **Konsumiert Queues**: `email`, `maintenance`, `transcription_pro` (korrekt für PRO-Tier).
- **Gesamte k3s-Pipeline re-getestet („der pipeline ist das k3s deployment das gesamte")**:
  - 16/16 Pods Running + Ready, Restarts stabil (nur livekit 1 alter Restart)
  - n8n: **7/7 Workflows ACTIVE**
  - Backend erreichbar (HTTP 401 auf geschützter Route = up), Frontend HTTP 200, TLS/Ingress aktiv
  - **E-Mail-Pipeline**: `POST /webhook/user-invited` → Execution **12 `status: success`** (Send-Email-Node fehlerfrei → Mail an `batniniabdelkader@yahoo.com` versendet). Gleicher Beweis wie Phase 169 (Execution 10), jetzt mit Phase-171-Worker-Umfeld.

## Fallbacks (nicht benötigt)
| FB | Trigger | Aktion |
|----|---------|--------|
| F1 | PRO weiter Crash-Loop nach Policy-Fix | `kubectl exec` in PRO-Pod: `bash -c '</dev/tcp/rabbitmq-staging/5672'` → bei „Connection refused" fehlt noch eine Policy-Zuweisung (K23 prüfen) |
| F2 | Egress ebenfalls blockiert | `default-deny-all` ist Ingress-only (`Policy Types: Ingress`) → Egress offen; nur Ingress-`From`-Listen ergänzen

---

# Phase 172: n8n meeting-created fromEmail Fix (2026-07-15)

## Status: ⚠️ TEILWEISE — DB-Fix angewendet + verifiziert (0 `.tn`, 550 weg), E-Mail-End-to-End-Versand NOCH NICHT bewiesen

## Problem
`meeting-created` sendete von `noreply@meeting-automation.tn` → Mailtrap `550 5.7.1 Sending from domain ...tn is not allowed` (Execution id=15, 18:56:45).

## Root Cause
Phase 151/169 hatten fromEmail nur in `user-invited` korrigiert (und fälschlich "5 Nodes gefixt" behauptet). `meeting-created` + 4 weitere (`transcription-completed`, `daily-reminders`/`escalations@`, `meeting-status-changed`, `pv-validated`) blieben auf `.tn` — DB in `workflow_entity` + `workflow_history` bewiesen.

## Fix
DB `UPDATE` (beide Tabellen, `json`-Spalte, `"workflowId"` gequotet) für `meeting-created` (id `91MtgrK1Nynd5oDS`): `noreply@meeting-automation.tn` → `noreply@meeting-automation.com`. `kubectl rollout restart deployment/n8n-staging`.

## Verifikation
- DB: 0 `.tn`-Zeilen für `meeting-created` ✅
- Execution `id=15` (vor Fix) `550=t`; `id=16` (nach Fix) `550=f` ✅ → Domain-Block weg

## OFFEN (ehrlich)
End-to-End E-Mail-Versand NICHT bewiesen: Test-Webhook `{"test":true}` scheiterte im Code-Node "Prepare Attendees" (`No attendees found in payload`), weil Payload keine `attendees` hatte. Finaler Beweis braucht echten Backend-Trigger (Meeting-Erstellung). 4 andere Workflows bleiben `.tn`/OFFEN.

## HARTE LESSON
- **"ACTIVE ≠ funktional" + niemals von 1 grünem Test auf "alle Workflows OK" schließen** — jeden Workflow einzeln real triggern + DB als Ground-Truth (`SELECT … LIKE '%@%.tn%'`).
- **n8n `workflow_history.workflowId` ist mixed-case** → in SQL quoten (`"workflowId"`); `nodes` ist `json` (nicht `jsonb`) → `::json`.
- **Dry-Run simuliert nur die DB-Änderung, nicht den E-Mail-Versand.**

---

# Phase 173: LiveKit Browser Signal Connection Fix (2026-07-15)

## Status: ✅ ABGESCHLOSSEN — Browser verbindet LiveKit-Signal (`wss://staging.meeting-automation.com/rtc`), bewiesen via `GET /rtc/validate?access_token=…` → HTTP 200 `"success"`

## Problem
Browser "test ME LIVE" → LiveKit Connection Error `could not establish signal connection: Abort handler called`. Server-seitige Egress lief (Räume erstellt), nur Browser-Signal brach ab.

## Root Cause (2 Ursachen)
1. **Ingress-Misroute**: `meeting-staging` routete `/rtc` + `/twirp` auf `backend:8000`; Backend hat keine `/rtc`-Route. Regression von Phase 56 (`.loop.md:795-799`), Ingress war auf `backend` revertiert.
2. **NetworkPolicy-Block**: `livekit-policy` erlaubte 7880 nur von `livekit-egress-staging` + `backend`; extern (hostNetwork ingress-nginx) nur via `ipBlock 0.0.0.0/0` für 7881/3478, NICHT 7880.

## Fix
- **A**: `network-policies.yaml` `livekit-policy` `ipBlock 0.0.0.0/0` um Port **7880/tcp** erweitert → `kubectl apply`.
- **B**: `ingress-staging.yaml` (NEU, repo) `/rtc` + `/twirp` → `livekit-server-staging:7880`; Annotation `websocket-services: "backend, livekit-server-staging"` → `kubectl apply`.

## Verifikation
- `kubectl get ingress`: `/rtc → livekit-server-staging:7880` ✅
- `curl /rtc` → 404 **von livekit** (erreicht livekit, nicht backend) ✅
- nginx-Log: Request → `[livekit-server-staging-7880] 10.0.0.191:7880` ✅ (beweist NetworkPolicy erlaubt 7880)
- `curl /rtc/validate?access_token=<gültiges Token>` → **HTTP 200 `"success"`** ✅ (End-to-End)

## HARTE LESSON
- **Ingress `/rtc` + `/twirp` MÜSSEN auf `livekit-server-staging:7880`** — Backend spricht `/rtc` nicht.
- **`livekit-policy` `ipBlock 0.0.0.0/0` braucht Port 7880** (Signal). 7881/3478 allein reicht nicht.
- **Regression = Ursache suchen** (wer hat Ingress auf `backend` revertiert?), nicht nur Symptom neu setzen.

---

# Phase 174: celery-worker-staging OOMKilled → Pipeline hang (2026-07-15)

## Status: ✅ ABGESCHLOSSEN — Free-Tier-Transkription läuft wieder; Recording `64831835-…` → `completed`, 1 Transcription-Row, Worker 0 Restarts

## Problem (Symptom)
Test-Meeting (free tier) aufgenommen → UI hängt bei "Recording → Processing insights… → Gladia → Mistral", `No transcription yet`. Frontend pollt `GET /recordings` alle ~20s endlos.

## Root Cause (bewiesen)
- `celery-worker-staging` (konsumiert Queue **`transcription_gratuit`**) hat **Memory-Limit 1Gi** (requests 512Mi) bei **4× prefork** → beim Laden des Audio + Gladia/Diarization/Mistral **OOMKilled (Exit 137)**.
- Task wird wegen `task_acks_late=True` (celery_app.py:22) redelivered → läuft erneut → OOM → **Crash-Loop**. Recording bleibt auf `transcribing` (nie `completed`).
- `celery-worker-pro-staging` (Queue `transcription_pro`) hat **3Gi** Limit + 0 Restarts = stabil — verarbeitet aber NUR Pro-Meetings, nicht die free-tier Tests.
- Beweis: `kubectl describe` → `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`; `celery inspect active` → task `redelivered: True, acknowledged: False`; DB `recordings.status = transcribing`.

## Fix
`infrastructure/kubernetes/staging/celery-worker-deployment.yaml` (Resources) — Memory an PRO-Tier angeglichen:
```
requests.memory: "512Mi" → "1500Mi"
limits.memory:   "1Gi"   → "3Gi"
```
`kubectl apply -f …/celery-worker-deployment.yaml` → Rolling-Restart (neue Pods `6657d664f-*`).

## Verifikation
- Rollout success, neue Pods **0 Restarts** ✅
- Task `cd456b1a-…` (Recording `64831835-1822-4a7c-bdb3-cced8aaaaadc`) redelivered → auf 3Gi-Worker ausgeführt → **Recording `status=completed`** ✅
- `transcriptions`-Tabelle: **1 Row** für das Recording (Gladia lief) ✅
- `celery inspect active`: 0 aktive `process_recording`-Tasks ✅

## HARTE LESSON
- **Free-Tier-Worker (`gratuit`) braucht GENAUSO VIEL Memory wie PRO-Tier** — beide verarbeiten identische Audio-/Gladia-/Mistral-Last. Limit 1Gi vs 3Gi ist die einzige Differenz, die den Hang verursacht.
- **OOM-Crash-Loop zeigt sich im Frontend als "hängt"/endlose Polling** — nicht als Error. Bei verdächtigem Hang sofort `kubectl describe <pod>` auf `Reason: OOMKilled` prüfen.
- **`task_acks_late=True` + `worker_prefetch_multiplier=1` (celery_app.py:22-23) rettet hier**: Task wird nach Worker-Tod zuverlässig redelivered und läuft nach Ressourcen-Fix von selbst zu Ende — kein manuelles Re-Trigger nötig.
- **Memory-Limits müssen zwischen Tiers konsistent sein** (K23-Ergänzung): ein neuer/anderer Worker-Tier darf nicht mit kleinerem Limit deployed werden als der Last-Profil erfordert.

---

# Phase 175: Plan-Fallback (Stripe-frei) + Pipeline-Queue-Routing Fix (2026-07-15/16)

## Status: ✅ ABGESCHLOSSEN — PRO-Kunde kann via UI upgraden OHNE Stripe + PRO-Meetings landen auf PRO-Worker (Sentinel LLM aktiv)

### Teil A: Admin-/Self-Service-Fallback für Planwechsel ohne Stripe
- **Problem**: GRATUIT-Kunde ohne `stripe_subscription_id` konnte nicht upgraden — `switch_plan` warf Hard-Block.
- **Fix** (`billing_service.py`): Stripe-Sub-Pflicht entfernt → Mock-Pfad (DB-Write + Audit `PLAN_SWITCH_MOCK`). "Already on plan"-Guard nur bei echter Stripe-Verbindung. `get_usage_status` liefert `stripe_subscription_id`.
- **Fix** (`frontend/src/pages/billing/BillingPanel.tsx`): `handleUpgrade` nutzt Fallback bei `!usage?.stripe_subscription_id` (robust, unabhängig von `usage`-Ladestatus). Fehler sichtbar als Snackbar.
- **E2E** (live Staging): DG-Login `bkta3beispiel@googlemail.com` → `POST /billing/switch-plan {plan:PRO}` → `mock_switched`. `usage-status`: GRATUIT/120 → **PRO/1800**. DB: `subscription_plan=PRO`, Audit `PLAN_SWITCH_MOCK`. Kunde erscheint in `/admin/clients` als PRO.

### Teil B: Queue-Routing-Bug (kritisch für PRO-Features)
- **Problem (bewiesen)**: `get_transcription_queue` (celery_app.py:78) verglich `plan.value in ("pro","entrepise")` — **lowercase**. Aber `SubscriptionPlan.PRO.value = "PRO"` (client.py:19, Großbuchstaben). → Vergleich matchte NIE → jeder PRO/ENTREPRISE-Kunde landete auf `transcription_gratuit`-Queue → GRATUIT-Worker (kein Sentinel LLM-Modell geladen).
- **Beweis**: Task `66a830a4` (TEST AIT, seit 23:06 PRO) wurde vom **GRATUIT-Worker** empfangen, nicht vom PRO-Worker. PRO-Worker sah ihn nie.
- **Folge**: Sentinel LLM (BAUPLAN Feature-Matrix Zeile 28) kam bei PRO-Kunden faktisch nicht an, obwohl `transcription_tasks.py:336` korrekt `plan == GRATUIT` prüft — der Task lief auf dem falschen Worker.
- **Fix** (celery_app.py:78 + :96): `plan.value.upper() in ("PRO", "ENTREPRISE")` (case-insensitive + korrekte Schreibung).
- **Verifikation (live Staging)**:
  - `get_transcription_queue('5a8add21-...', db)` → **`transcription_pro`** ✅
  - Test-Task in `transcription_pro` dispatchert → **PRO-Worker empfing** (`received` im PRO-Pod), GRATUIT-Worker sah ihn NICHT ✅
  - Damit: PRO-Meetings laufen auf PRO-Worker → Sentinel LLM (Qwen-1.5B) aktiv (Log: `Plan PRO — using Sentinel LLM`), ONNX Speaker-ID ohnehin plan-unabhängig aktiv.

### Deploy
- Backend-Image rebuild (`batnini/meeting-automation-backend:latest`) → k3s import → rollout-restart: `backend`, `celery-worker-staging` (GRATUIT), `celery-worker-pro-staging`. Alle 3 successfully rolled out ✅

### HARTE LESSON (neu)
- **P1 — Enum-Vergleich MUSS case-insensitive + exakte Werte**: `SubscriptionPlan.PRO.value == "PRO"` (Großbuchstaben). Queue-Routing/String-Vergleiche gegen Enum-Werte dürfen niemals hartkodierte Lowercase-Literals (`"pro"`) nutzen — `plan.value.upper() in (...)` oder `plan == SubscriptionPlan.PRO`. Sonst routen ALLE PRO/ENT-Kunden auf den falschen Worker und PRO-Features (Sentinel LLM) greifen nie.
- **P2 — Queue-Routing ist die Voraussetzung für Feature-Gating**: Sentinel/ONNX/LLM sind nur auf dem richtigen Worker verfügbar. Ein Routing-Bug macht das Feature-Matrix-Versprechen (BAUPLAN Zeile 28-29) faktisch ungültig, OHNE dass ein Error auftritt.
- **P3 — Plan-Wechsel zur Laufzeit**: `get_transcription_queue` liest den Plan LIVE aus der DB (nicht gecached). Ein Kunde, der mitten in der Sitzung von GRATUIT→PRO wechselt, bekommt ab dem NÄCHSTEN Meeting den PRO-Worker — korrekt.
- **L34 (siehe .loop.md)**: Fragile Frontend-Condition im Upgrade-Flow verhindert Fallback still — Fallback immer bei `!usage?.stripe_subscription_id`.

---

# Plan-Referenz: LiveKit Signal + n8n SMTP (2026-07-16)

## Status: ✅ AUSGEFÜHRT (siehe Phase 169 + 173)

Plan-Datei: `.mimocode/plans/1782956362564-playful-wizard.md`

| Problem | Phase | Status |
|---------|-------|--------|
| LiveKit "could not establish signal connection" | Phase 173 | ✅ ABGESCHLOSSEN — Ingress `/rtc`→livekit-server:7880, NetworkPolicy Port 7880 added |
| n8n SMTP Credential Referenz (alte IDs in JSON) | Phase 169 | ✅ ABGESCHLOSSEN — Credential `nTNtib8Ge4k4Wjv9` in DB, Workflow-Nodes updated |
|

---

# Phase 181: CI/CD Pipeline Korrektur + Production-Manifests (2026-07-17)

## Status: ✅ IMPLEMENTIERT (2026-07-17) — e2e-tests.yml repariert + `infrastructure/kubernetes/production/` angelegt (30 Dateien, YAML validiert). KEINE Commits ohne Order.

## Ziel
1. `e2e-tests.yml` reparieren (10 Probleme, siehe `.loop.md` Phase 181 Tabelle)
2. `infrastructure/kubernetes/production/` anlegen (Deployment-Problem #7): Job 3 zeigt auf `infrastructure/kubernetes/production/`

## Production-Manifests (geplant, abgeleitet aus `staging/`)
| Datei | Inhalt | Unterschied zu Staging |
|-------|--------|------------------------|
| `namespace.yaml` | `meeting-automation` | ohne `-staging` |
| `cnpg-cluster.yaml` | `meeting-db`, 3 instances, 10Gi, backup 90d | 2→3 instances, retention 30d→90d |
| `backend-deployment.yaml` | 3 replicas, `imagePullPolicy: IfNotPresent` | 2→3 replicas |
| `frontend-deployment.yaml` | 3 replicas | 2→3 replica |
| `celery-worker-deployment.yaml` | 3 replicas, 3Gi | GRATUIT-Tier |
| `celery-worker-pro-deployment.yaml` | 3 replicas, 3Gi | PRO/ENT-Tier |
| `celery-beat-deployment.yaml` | 1 replica | gleich |
| `ingress-prod.yaml` | nginx-ingress, host `meeting-automation.com`, TLS `prod-tls` | Host + TLS-Secret anders |
| `backend-secrets.yaml` | Templates (aus Staging, ohne harte Werte) | Secrets aus `KUBE_CONFIG_PRODUCTION` Cluster |
| `backend-config.yaml` | Config (aus Staging) | angepasst |
| `network-policies.yaml` | `app: meeting-db` (nicht `postgres-staging`) | Selector angepasst |
| **Entfernt** | `postgres-statefulset.yaml` | CNPG ersetzt |

## Entscheidungen (bestätigt)
- **#2 SKIP_SENTINEL**: KOMPLETT ENTFERNEN (C7-Konform, nie Staging/Prod; ~80min CI-Build akzeptiert)
- **#7 Production-Dir**: ANLEGEN (nicht Job 3 deaktivieren). Prod = separate Cluster (`KUBE_CONFIG_PRODUCTION` existiert)
- **Ingress**: nginx-ingress (wie Staging), NICHT Traefik (Traefik-YAMLs existieren nicht im Repo)

## CI-Fixes (Zeilennummern aus aktueller `e2e-tests.yml`)
| # | Zeile | Fix |
|---|-------|-----|
| 1 | 26 | `docker build` Schritt ENTFERNEN (nur build-push-action) |
| 2 | 26, 73 | `SKIP_SENTINEL=true` aus beiden Builds ENTFERNEN |
| 3 | 165, 182, 216 | `staging.meeting-automate.tn` → `staging.meeting-automation.com` |
| 4 | 235 | `svc/postgres-staging` → `svc/meeting-db-rw` (CNPG ReadWrite Service) |
| 5 | 264 | `--env=staging` ENTFERNEN (pytest kennt flag nicht) |
| 6 | 272 | `DATABASE_URL: ${{ env.DATABASE_URL }}` ENTFERNEN (vermeidet Secret-Leak in Logs; CNPG via K8s-Secret) |
| 7 | 340 | `infrastructure/kubernetes/` → `infrastructure/kubernetes/production/` |
| 9 | 193-206 | `consents`-Block (4× true) zur Register-Payload hinzufügen |
| 10 | 163-164 | `traefik-*.yaml` → `ingress-staging.yaml` (nginx) |
| 8 | — | Pipeline nutzt kein `gh` → OK (nur Lokaldoku) |

## Verifikation (nach Implementierung)
- `e2e-tests.yml` YAML-lint (GitHub Actions validiert bei Push)
- Production-Manifests: `kubectl --dry-run=client apply -f infrastructure/kubernetes/production/` (lokal mit Prod-kubeconfig, falls verfügbar)
- KEINE Commits ohne expliziten Order.

---

## Phase 181 NACHTRAG — creator_id-Bug (verifiziert)

**Schritt 2b (zusätzlich, nach Sim entdeckt)**: `livekit.py:427` nutzte
`recording.creator_id` (existiert NICHT auf Recording-Model) → AttributeError →
HTTP 500 → process_recording nie enqueued. TATAI-Hang war dies, nicht Webhook-Routing.
Fix: `meeting = await db.get(Meeting, meeting_id)`; `meeting.creator_id` verwenden.
Backend neu gebaut (no SKIP_SENTINEL) → k3s import → rollout backend+celery*.

**3-Meeting-Sim (nach Fix)**: alle 3 Webhooks HTTP 200, arrived YES, process_recording
enqueued + gestartet. GRATUIT→`transcription_gratuit` (worker-staging);
PRO+ENTREPRISE→`transcription_pro` (worker-pro-staging). Keine 500/Tracebacks.
Sim-Recordings `failed` (MinIO-Download Sim-File) — erwartet. Cleanup: alle →failed/CANCELLED.

 **Offener Punkt**: ENTREPRISE nutzt `transcription_pro` (kein eigener Queue). Ggf. ergänzen.

## Phase 182: OnlyOffice "Download failed" beim PV-Öffnen (2026-07-17, FIXED 2026-07-18)

**Status**: ✅ GEFIXT + DEPLOYED — Root-Cause git-bewiesen: Regression von Phase 64, die
`/doc/`-WebSocket-Route (OnlyOffice v9.4.0 Realtime-Handshake) beim Frontend-Rebuild verloren ging.
ConfigMap (`frontend-nginx-config`) + Ingress (`ingress-staging.yaml`) korrigiert, Frontend rollout.
Verifiziert: `/doc/` → OnlyOffice Socket.IO (HTTP 400 `Transport unknown` statt SPA-HTML),
`/web-apps/` → 403 (OnlyOffice), `/healthcheck` → 200.

**Root Cause (git-bewiesene Regression, R1)**:
- OnlyOffice **v9.4.0** nutzt **Socket.IO auf Pfad `/doc/`** (NICHT `/socket.io/`) für die
  Echtzeit-Verbindung zum Document-Server (WebSocket-Handshake).
- **Phase 64 (Commit `58db59cf`)** hatte `/doc/` WebSocket-Proxy im Frontend-nginx hinzugefügt
  (funktional bis ~09.07). Bei späterem Frontend-Rebuild (nach 09.07, z.B. `d8758e69`) ging die
  Regel verloren → Regression.
- **Beweis**: `git log -S 'location /doc/'` → Phase 64 fügte sie hinzu; `git grep 'location /doc/'`
  heute → nur Docs, KEIN nginx-File. `curl https://staging.meeting-automation.com/doc/` lieferte
  `<!DOCTYPE html>` (SPA) statt Handshake → OnlyOffice "Download failed".
- **Backend-Download ist SAUBER** (widerlegte Gegen-Hypothese): `200 + docx + CORS: *`,
  JWT-Secret matcht. `document.url` wird vom **Backend** (Document-Server) geladen, nicht vom
  Browser → interne `ONLYOFFICE_BACKEND_URL` korrekt (O1/O2-Hypothese verworfen).

**Fix (DEPLOYED)**:
| # | Datei | Änderung |
|---|-------|----------|
| 1 | `infrastructure/kubernetes/frontend-nginx-config.yaml` | `location /doc/` + `/web-apps/` + `/cache/` + versioniert + `/healthcheck` → `onlyoffice-staging.meeting-automation-staging.svc.cluster.local:80` (WebSocket-Upgrade) |
| 2 | `infrastructure/kubernetes/staging/ingress-staging.yaml` | `/doc`, `/web-apps`, `/cache`, `/healthcheck` → `onlyoffice-staging:80`; `websocket-services` + `onlyoffice-staging` |
| 3 | `backend/app/api/v1/pv.py:403` | Revertiert auf `ONLYOFFICE_BACKEND_URL` (intern) — Download war nie das Problem |

**Verifiziert (live)**:
- `curl /doc/` → HTTP 400 `{"code":0,"message":"Transport unknown"}` (OnlyOffice Socket.IO, nicht SPA)
- `curl /web-apps/` → HTTP 403 (OnlyOffice), `curl /healthcheck` → HTTP 200
- Frontend rollout successful (ConfigMap gemountet, nginx reload)

**HARTE LESSON (L26 — Regression)**:
- **R1** — OnlyOffice v9.4.0 Realtime = Socket.IO auf `/doc/` (nicht `/socket.io/`). Frontend-nginx
  MUSS `location /doc/` mit WebSocket-Upgrade → OnlyOffice proxien.
- **R2** — Bei jedem Frontend-Rebuild die OnlyOffice-Routen (`/doc/`, `/web-apps/`, `/cache/`,
  versioniert, `/healthcheck`) explizit verifizieren (grep nginx.conf + `curl /doc/` nach Deploy).
  "Löschen ist verboten" gilt auch für Config-Regressionen: Ursache (verlorene Route) fixen,
  nicht den Editor neu bauen.
- **O1/O2 WIDERLEGT** — `document.url` wird vom Backend (Document-Server) geladen, nicht vom Browser.
  Interne `ONLYOFFICE_BACKEND_URL` korrekt; PUBLIC_BACKEND_URL war falscher Ansatz (→ ECONNREFUSED).

---

# Phase 187: celery-worker-pro-staging Missing nach k3s Reinstall (2026-07-31)

## Status: 🔴 OFFEN — PRO/ENTREPRISE Queue-Routing defekt

## Problem

| Symptom | Beweis |
|---------|--------|
| `celery-worker-pro-staging` Deployment existiert nicht in k3s | `kubectl get deploy -n meeting-automation-staging` → kein `celery-worker-pro-staging` |
| PRO/ENTREPRISE Recordings landen in `transcription_pro` Queue mit 0 Consumers | `kubectl exec rabbitmq-staging-0 -- rabbitmqctl list_queues name messages consumers` → `transcription_pro` hat Messages aber 0 Consumers |
| GRATUIT Worker läuft (2x) aber konsumiert NUR `transcription_gratuit` + `transcription` | Worker-Logs: Queues `transcription`, `transcription_gratuit`, `email`, `maintenance` |
| Sentinel LLM wird nie getriggert (braucht PRO Worker) | Kein `Sentinel` oder `TIMING` Log-Eintrag |

## Root Cause

**`setup-kubernetes-staging.sh` hat `celery-worker-pro-deployment.yaml` NICHT in der MANIFESTS-Liste.**

Das Script deployt nur:
- `celery-worker-deployment.yaml` (GRATUIT) ✅
- `celery-beat-deployment.yaml` ✅
- **FEHLT:** `celery-worker-pro-deployment.yaml` ❌

Nach k3s Reinstall + `bash setup-kubernetes-staging.sh` wurde PRO Worker nie erstellt.

## Auswirkung

| Tenant | Queue | Worker vorhanden? | Pipeline funktional? |
|--------|-------|-------------------|---------------------|
| GRATUIT | `transcription_gratuit` | ✅ celery-worker-staging (2x) | ✅ Ja (Fallback, kein LLM) |
| PRO | `transcription_pro` | ❌ FEHLT | ❌ Nein — Recording hängt auf `transcribing` |
| ENTREPRISE | `transcription_pro` | ❌ FEHLT | ❌ Nein — Recording hängt auf `transcribing` |

## Plan

### Schritt 1: Script fixen (1 Zeile)

**Datei:** `scripts/setup-staging-cluster.sh`
**Änderung:** `celery-worker-pro-deployment.yaml` zur MANIFESTS-Liste hinzufügen

```bash
# VORHER (MANIFESTS-Liste):
MANIFESTS=(
    ...
    "celery-worker-deployment.yaml"
    "celery-beat-deployment.yaml"
    "backend-deployment.yaml"
    ...
)

# NACHHER:
MANIFESTS=(
    ...
    "celery-worker-deployment.yaml"
    "celery-worker-pro-deployment.yaml"    # ← NEU
    "celery-beat-deployment.yaml"
    "backend-deployment.yaml"
    ...
)
```

### Schritt 2: NetworkPolicies prüfen (K23)

`celery-worker-pro-staging` braucht `podSelector` in:
- `rabbitmq-policy` (From)
- `redis-policy` (From)
- `postgres-policy` (From)
- `minio-policy` (From)
- `cnpg-policy` (From)

Beweis: Phase 171 hat genau daran versagt (226 Restarts, Connection refused).

### Schritt 3: Image + Import + Deploy

```bash
# Image muss bereits existieren (SKIP_SENTINEL=false)
# Nur Deploy:
kubectl apply -f infrastructure/kubernetes/staging/celery-worker-pro-deployment.yaml -n meeting-automation-staging
```

### Schritt 4: Verifikation

```bash
# 1. Pod Status
kubectl get pods -n meeting-automation-staging | grep celery-worker-pro
# Erwartung: 1/1 Running, 0 Restarts

# 2. Worker Ready
kubectl logs deployment/celery-worker-pro-staging -n meeting-automation-staging --tail=5 | grep ready
# Erwartung: celery@celery-worker-pro-staging-... ready.

# 3. Queue Consumers
kubectl exec rabbitmq-staging-0 -n meeting-automation-staging -- rabbitmqctl list_queues name messages consumers | grep transcription_pro
# Erwartung: transcription_pro    X    1 (oder 2)

# 4. Sentinel Init (bei erstem PRO Recording)
kubectl logs deployment/celery-worker-pro-staging -n meeting-automation-staging | grep -i sentinel
# Erwartung: Sentinel (Qwen-1.5B) initialized successfully
```

## Zusammenhang mit docker-compose

| Umgebung | Config-Datei | celery-worker? | celery-worker-pro? |
|----------|-------------|----------------|--------------------|
| Lokales Staging | `docker-compose.yml` | ✅ Service definiert | ❌ Nicht separat (eine Queue reicht lokal) |
| E2E Tests | `docker-compose.e2e.yml` | ❌ Fehlt (nicht nötig, E2E_TEST=true = eager mode) | ❌ Fehlt |
| k3s Staging | `setup-kubernetes-staging.sh` + YAMLs | ✅ `celery-worker-deployment.yaml` | ❌ **FEHLT im Script** |

## HARTE LESSON

- **K24 — `setup-kubernetes-staging.sh` MUSS ALLE Worker-Tiers in der MANIFESTS-Liste haben**: Das Script war ursprünglich für ein-Tier-Setup gebaut (Phase 159 fügte PRO Worker hinzu, aber vergaß das Script zu updaten). Jeder neue Worker-Tier MUSS in die MANIFESTS-Liste eingetragen werden.
- **K25 — k3s Reinstall verliert ALLE Deployments**: PVCs bleiben (local-path), aber Deployments/Services/Secrets/ConfigMaps gehen verloren. Nach jedem k3s Reinstall MUSS `setup-kubernetes-staging.sh` komplett durchlaufen — und das Script muss ALLES enthalten.

## Offene Punkte

| # | Punkt | Status |
|---|-------|--------|
| 1 | `setup-kubernetes-staging.sh` fixen (1 Zeile) | ⏳ Offen |
| 2 | NetworkPolicies für PRO Worker prüfen/ergänzen | ⏳ Offen |
| 3 | PRO Worker in k3s deployen | ⏳ Offen |
| 4 | E2E Pipeline-Test (PRO Recording → Sentinel → PV) | ⏳ Offen |
| 5 | GRATUIT Queue-Routing Test (15-Min-Limit) | ⏳ Offen |

---

# Phase 188: Manual Tenant Activation (2026-07-31)

## Status: ✅ ABGESCHLOSSEN — 8/8 E2E Tests bestanden, Backend + Frontend deployed

## Problem
Kunde wählt auf Landing Page ein Abo (GRATUIT/PRO/ENTREPRISE), registriert sich, und kann sofort einloggen. Es gibt keinen Admin-Approval-Prozess. Jeder neue Tenant ist sofort aktiv — ohne Vertragsklärung, Zahlung oder Admin-Freigabe.

## Ziel
Manueller Aktivierungs-Flow: Kunde registriert sich → aktiviert Account per Email → **kann sich aber NICHT einloggen** → ruft Admin an → Admin aktiviert Client im Dashboard → Kunde kann die App nutzen.

## User Journey
```
Kunde → Landing Page → /register?plan=PRO → Formular
  → Backend: Client(PENDING) + User(PENDING)
  → Email #1: "Aktivieren Sie Ihren Account" (Aktivierungs-Link)
  → Kunde klickt Link → setzt Passwort → User wird ACTIVE
  
  ABER: Kunde kann sich NOCH NICHT einloggen!
  → Login gibt HTTP 403: "Bitte kontaktieren Sie den Administrator"
  
  → Kunde ruft Admin an → erklärt Abo + Zahlung
  → Admin aktiviert Client im Dashboard (/admin/clients)
  → Email #2 an Kunde via n8n: "Ihr Abo wurde aktiviert"
  → Kunde kann sich jetzt einloggen und die App nutzen
```

## Technische Analyse (10/10 verifiziert gegen echten Code)

| # | Claim | Code-Beweis | Verifiziert |
|---|-------|-------------|-------------|
| 1 | `create_client()` Default `status=ACTIVE` | `client_service.py:43` | ✅ |
| 2 | Login prüft nur `user.status`, NICHT `client.subscription_status` | `auth.py:194` | ✅ |
| 3 | `PATCH /admin/clients/{id}/status` existiert | `admin.py:100` | ✅ |
| 4 | `adminService.updateClientStatus()` existiert | `adminService.ts:41` | ✅ |
| 5 | ClientList Activate-Button funktioniert mit PENDING | `ClientList.tsx:48,108` | ✅ |
| 6 | AdminDashboard PENDING-KPI existiert | `AdminDashboard.tsx:108` | ✅ |
| 7 | Landing Page übergibt keinen Plan-Parameter | `LandingPage.tsx:430` | ✅ |
| 8 | n8n Webhook Pattern funktioniert (SMTP + n8n) | `email_tasks.py:150` | ✅ |
| 9 | E2E Bypass (`_e2e`) existiert | `auth.py:303` | ✅ |
| 10 | `SubscriptionStatus.PENDING` Enum existiert | `client.py:24` | ✅ |

## Was BEREITS existiert (NICHT ändern)

| Komponente | Beweis |
|------------|--------|
| ClientList "Activate" Button | `ClientList.tsx:48-56` — toggelt ACTIVE/DISABLED, PENDING→ACTIVE funktioniert |
| AdminDashboard "Pending Clients" KPI | `AdminDashboard.tsx:108` — `stats.status_distribution['PENDING']` |
| ClientDetails Status-Chip (gelb) | `ClientDetails.tsx:68` — PENDING=warning, ACTIVE=success |
| `PATCH /admin/clients/{id}/status` Endpoint | `admin.py:100` — akzeptiert jeden SubscriptionStatus + Audit-Log |
| `adminService.updateClientStatus()` | `adminService.ts:41` — `api.patch(/admin/clients/${id}/status, {status})` |
| `SubscriptionStatus.PENDING` Enum | `client.py:24` |
| n8n Webhook `user-invited` (SMTP + n8n Fallback) | `email_tasks.py:150-158` |
| CheckEmailPage (Aktivierungs-Link + Resend) | `CheckEmailPage.tsx` |
| ConsentDialog | Bleibt wie ist |
| Stripe Webhook (setzt ACTIVE nach Bezahlung) | Bleibt korrekt |

## Schritt-für-Schritt Plan (5 Dateien, ~55 Zeilen)

| # | Datei | Zeile | Änderung | Zeilen |
|---|-------|-------|----------|--------|
| 1 | `backend/app/services/client_service.py` | 43 | Default `status=SubscriptionStatus.ACTIVE` → `SubscriptionStatus.PENDING` | 1 |
| 2 | `backend/app/api/v1/auth.py` | ~196 | Login-Gate: Nach User-Status-Check prüfen `client.subscription_status != ACTIVE` → HTTP 403 | 5 |
| 3 | `backend/app/api/v1/auth.py` | ~345 | Admin-Notification: `send_admin_new_tenant_notification.delay(client_id, company_name, plan, email)` | 3 |
| 4 | `backend/app/tasks/email_tasks.py` | neu | Neuer Celery Task: `send_admin_new_tenant_notification` → n8n Webhook `admin-new-tenant` → Email an Admin | 30 |
| 5 | `backend/app/core/config.py` | ~63 | `N8N_WEBHOOK_ADMIN_NEW_TENANT = "http://n8n:5678/webhook/admin-new-tenant"` | 1 |
| 6 | `backend/app/api/v1/admin.py` | ~110 | In `update_client_status`: wenn PENDING→ACTIVE, `send_customer_activated_email.delay(email, name)` triggern | 10 |
| 7 | `backend/app/tasks/email_tasks.py` | neu | Neuer Celery Task: `send_customer_activated_email` → n8n Webhook `customer-activated` → Email an Kunde | 30 |
| 8 | `backend/app/core/config.py` | ~63 | `N8N_WEBHOOK_CUSTOMER_ACTIVATED = "http://n8n:5678/webhook/customer-activated"` | 1 |
| 9 | `frontend/src/pages/LandingPage.tsx` | 430 | Pricing-Buttons: `navigate('/register?plan=GRATUIT')` / `?plan=PRO` / `?plan=ENTREPRISE` | 3 |
| 10 | `backend/app/api/v1/auth.py` | ~305 | E2E Bypass: `client_status = SubscriptionStatus.ACTIVE if _e2e else SubscriptionStatus.PENDING` | 2 |

## n8n Workflows (2 neue)

### Workflow 1: `admin-new-tenant`
```
Trigger: Webhook POST /webhook/admin-new-tenant
Body: { company_name, plan, email, client_id }
Action: SendGrid/SMTP → admin@meeting.tn
Subject: "Neuer Kunde: {company_name} ({plan}) wartet auf Aktivierung"
Body: Link zu /admin/clients/{client_id}
```

### Workflow 2: `customer-activated`
```
Trigger: Webhook POST /webhook/customer-activated
Body: { email, full_name, company_name }
Action: SendGrid/SMTP → {email}
Subject: "Ihr Abo wurde aktiviert"
Body: "Sie können sich jetzt einloggen: {login_url}"
```

## Login-Gate (Schritt 2 — KRITISCH)
```python
# auth.py login endpoint — NACH user.status Check (~Zeile 196)
from app.models.client import Client, SubscriptionStatus
client_result = await db.execute(select(Client).where(Client.id == user.client_id))
client = client_result.scalar_one_or_none()
if client and client.subscription_status != SubscriptionStatus.ACTIVE:
    raise HTTPException(
        status_code=403,
        detail="Ihr Abo wartet auf Aktivierung. Bitte kontaktieren Sie den Administrator."
    )
```

## Betroffene Tests

| Test | Problem | Lösung |
|------|---------|--------|
| `test_auth.py` | Registration erwartet Client=ACTIVE | `E2E_TEST=true` Bypass |
| `conftest.py` Fixtures | Clients mit ACTIVE | Fixtures bleiben (Test-Clients sind aktiv) |
| 365 E2E Tests | Erwarten funktionierenden Login | `E2E_TEST=true` → Client=ACTIVE |

## Zusammenfassung

| Aspekt | Detail |
|--------|--------|
| Dateien geändert | 5 (client_service.py, auth.py, email_tasks.py, config.py, admin.py, LandingPage.tsx) |
| Neue Dateien | 0 |
| Neue n8n Workflows | 2 (admin-new-tenant, customer-activated) |
| Bestehende Tests | 365 — unverändert (E2E Bypass) |
| Enum-Änderungen | 0 (PENDING existiert bereits) |
| DB-Migration | 0 (Schema unverändert) |
| Frontend-Änderungen | 1 Datei (LandingPage.tsx — 3 Zeilen) |
| Gesamt Zeilen Code | ~55 Zeilen |

## Offene Fragen

| # | Frage | Antwort (Stand 2026-07-31) |
|---|-------|---------------------------|
| 1 | Welche Pläne brauchen Admin-Aktivierung? | **ALLE** (GRATUIT, PRO, ENTREPRISE) |
| 2 | Wer ist der Admin? | **system_admin** Rolle (Dashboard: /admin) |
| 3 | Wie wird Admin benachrichtigt? | **n8n Webhook → Email** an admin@meeting.tn |
| 4 | Login-Gate oder Banner? | **Login-Gate** — Kunde kann sich erst einloggen NACH Admin-Aktivierung |
