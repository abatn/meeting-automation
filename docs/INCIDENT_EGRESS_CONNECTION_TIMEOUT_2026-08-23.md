# Incident Report: LiveKit Egress Connection Timeout

**Datum:** 2026-08-23
**Status:** 🔴 OPEN — nicht behoben
**Schweregrad:** P1 — Recording-Feature komplett funktionsunfähig
**Betroffen:** Production (169.58.83.32)
**Agent:** Buffy (Freebuff)

---

## 1. Zusammenfassung

LiveKit Egress kann nach Pod-Restart keine WebRTC-Verbindung zum LiveKit-Server aufbauen. Das Recording schlägt fehl (`EGRESS_FAILED: "could not connect after timeout"`). Stop-Recording-Button funktioniert nicht, weil kein Recording aktiv ist.

**Funktioniert:** Recording `7cc15aba` am 22.08.2026 20:52 UTC (Pods ~36h alt)
**Kaputt:** Recording `6b96c1af` am 23.08.2026 14:02 UTC (Pods ~1h alt nach Restart)

---

## 2. Timeline

| Zeit (UTC) | Event | Status |
|------------|-------|--------|
| 22.08. 20:52 | Recording `7cc15aba` — ERFOLGREICH (460s Pipeline) | ✅ |
| 23.08. 13:00 | CI/CD Deploy Production (`cd0116d6` — Port-Forward Fix) | ✅ |
| 23.08. 13:12 | `03-deploy-livekit.sh` ausgeführt → Pods neu gestartet | ✅ |
| 23.08. 13:12 | Egress Pod `845fc9bcb-g7l74` erstellt (Alter: 0) | ✅ |
| 23.08. 13:12 | Server Pod `7d67bd48d4-2xxlf` erstellt (Alter: 0) | ✅ |
| 23.08. 14:02:43 | Room `1a69ee87...` erstellt (User startet Meeting) | ✅ |
| 23.08. 14:02:46 | Participant joined (Browser: Firefox 154.0) | ✅ |
| 23.08. 14:02:50 | Egress gestartet (`EG_EHJHZ9cV7WgR`) | ✅ |
| 23.08. 14:02:51 | Server empfängt Egress-Participant (WebSocket ✅) | ✅ |
| **23.08. 14:02:56** | **🔴 Egress ICE Agent Closed — "could not connect after timeout" (4.5s)** | ❌ |
| 23.08. 14:02:56 | Server entfernt Egress: `CLIENT_REQUEST_LEAVE` | ❌ |
| 23.08. 14:02:56 | Recording `6b96c1af` Status: `failed` | ❌ |
| 23.08. 14:03:28 | Stop-Recording aufgerufen (1. Versuch) — kein Aktives Recording | ⚠️ |
| 23.08. 14:03:56 | Stop-Recording aufgerufen (2. Versuch) — kein Aktives Recording | ⚠️ |

---

## 3. Bewiesene Fakten

### 3.1 Was wurde geändert

| Komponente | Vorher (22.08. 20:52) | Jetzt (23.08. 14:02) | Status |
|------------|----------------------|----------------------|--------|
| Server Image | `livekit-server:v1.9.0` | `livekit-server:v1.9.0` | ⚪ GLEICH |
| Egress Image | `egress:v1.14.1` | `egress:v1.14.1` | ⚪ GLEICH |
| Server hostNetwork | `true` | `true` | ⚪ GLEICH |
| Egress hostNetwork | `true` | `true` | ⚪ GLEICH |
| Server ConfigMap | `livekit-server` (Helm) | `livekit-server` (Helm) | ⚪ GLEICH |
| Egress ConfigMap | `livekit-egress` (Helm) | `livekit-egress` (Helm) | ⚪ GLEICH |
| Server Pod Age | **~36h** | **~1h** | 🔴 GEÄNDERT |
| Egress Pod Age | **~36h** | **~1h** | 🔴 GEÄNDERT |
| Helm Charts | `livekit-server-1.9.0.tgz`, `egress-1.8.4.tgz` | GLEICHE Charts | ⚪ GLEICH |

**Fazit:** Einzig geänderter Faktor = Pod-Restart (Alter 36h → 1h).

### 3.2 Was NICHT geändert wurde

- Kein Git-Commit seit `11fa7e7b` (20.08.) der LiveKit-Dateien betrifft
- Keine Config-Änderungen (ws_url, api_key, redis, s3 — alles identisch)
- Keine Version-Änderung (v1.9.0 / v1.14.1 — identisch)
- Keine Secrets geändert

### 3.3 Was die CI/CD Deploy getriggert hat

```
03-deploy-livekit.sh:
1. helm upgrade --install livekit-server  → gleicher Chart → KEIN Config-Unterschied
2. kubectl patch hostNetwork=true        → war schon gesetzt → KEIN Unterschied
3. kubectl rollout restart               → POD NEU GESTARTET ← EINZIGER UNTERSCHIED
4. helm upgrade --install livekit-egress → gleicher Chart → KEIN Config-Unterschied
5. kubectl patch hostNetwork=true        → war schon gesetzt → KEIN Unterschied
6. kubectl rollout restart               → POD NEU GESTARTET ← EINZIGER UNTERSCHIED
```

### 3.4 Egress Deployment Analyse

```
Container: egress (livekit/egress:v1.14.1)
hostNetwork: True
dnsPolicy: ClusterFirstWithHostNet
Volumes: 0
VolumeMounts: 0
Env Vars: 1 (EGRESS_CONFIG_BODY — Secret)
Command: N/A (Helm-default)
Args: N/A (Helm-default)
```

**ConfigMap `livekit-egress` (Helm-manual):**
```yaml
ws_url: ws://livekit-server:7880  # ✅ korrekt
api_key: prod-9a4ac9f989143b65    # ✅ korrekt
api_secret: prod-8f8b7b...        # ✅ korrekt
redis: redis.meeting-automation... # ✅ korrekt
s3: http://minio:9000              # ✅ korrekt
```

**ConfigMap `livekit-egress-config` (manuell, 20.08.):**
```yaml
# KEIN ws_url!  # ❌
# KEIN api_key! # ❌
# KEIN s3!      # ❌
room_composite_cpu_cost: 1.5  # ← Unterschied zu Helm (2.0)
```

**Beide ConfigMaps werden NICHT gemountet** — Egress nutzt `EGRESS_CONFIG_BODY` Secret.

### 3.5 Server Analyse

```
Container: livekit (livekit/livekit-server:v1.9.0)
hostNetwork: True
dnsPolicy: ClusterFirstWithHostNet
Ports: 7880 (HTTP), 7881 (TCP), 3478 (TURN/UDP), 50000-60000 (WebRTC UDP)
Resources: 500m-1000m CPU, 512Mi-1024Mi Memory
```

**Server ConfigMap:**
```yaml
port: 7880
room:
  departure_timeout: 60
  empty_timeout: 600
  max_participants: 10
rtc:
  allow_tcp_fallback: true
  force_tcp: false
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
turn:
  enabled: false
```

---

## 4. Egress-Fehler Analyse

### 4.1 Fehler-Logs (Egress)

```
2026-08-23T14:02:56.135Z WARN  failed to get server reflexive address udp6
  stun:stun1.l.google.com:19302: read udp6 [::]:42057: use of closed network connection

2026-08-23T14:02:56.135Z WARN  undeclaredMediaProcessor failed to open SrtpSession:
  the DTLS transport has not started yet

2026-08-23T14:02:56.241Z INFO  Setting new connection state: Closed

2026-08-23T14:02:56.241Z INFO  waiting for connection establishment failed
  error: "could not connect after timeout"
  url: "ws://livekit-server:7880"
  timeout: "4.548279372s"
  validateTimeout: "3s"
  ConnectTimeout: "5s"

2026-08-23T14:02:56.274Z INFO  egress_failed
  requestType: "room_composite"
  outputType: "file"
  error: "could not connect after timeout"
```

### 4.2 Server-Logs (gleicher Zeitraum)

```
14:02:50.897 — Egress.StartRoomCompositeEgress → 200 OK (1.79s)
14:02:51.013 — webhook: egress_started (EGRESS_STARTING)
14:02:51.463 — starting RTC session (egress participant PA_eBGqE8fMbApG)
14:02:56.101 — removing participant without connection (reason: CLIENT_REQUEST_LEAVE)
14:02:56.418 — webhook: egress_ended (EGRESS_FAILED, "could not connect after timeout")
```

### 4.3 Kette der Ereignisse

```
Egress startet
  → WebSocket zu ws://livekit-server:7880 ✅ (erfolgreich)
  → Server empfängt Egress-Participant ✅
  → ICE Agent startet Gathering
  → STUN-Request zu stun1.l.google.com:19302 ❌ (udp6 "use of closed network connection")
  → ICE Candidate Gathering scheitert
  → DTLS Transport kann nicht starten (kein ICE-Connect)
  → Timeout nach 4.548s
  → Egress gibt auf → CLIENT_REQUEST_LEAVE
  → Recording Status: failed
```

---

## 5. Staging vs Production Vergleich

### 5.1 Kritische Unterschiede

| Eigenschaft | Staging ✅ (funktioniert) | Production ❌ (kaputt) |
|-------------|--------------------------|------------------------|
| **Egress Image** | **`v1.8.4`** (Chart-Default) | **`v1.14.1`** (explizit gesetzt) |
| **Server Image** | `v1.9.0` | `v1.9.0` |
| **Egress CPU Limit** | **1 Core** | **2 Cores** |
| **Pod-Restart bei Deploy** | **NEIN** (Skip in `03-deploy-manifests.sh`) | **IMMER** (`kubectl rollout restart`) |
| **Egress Pod Age** | **3 Tage 20 Stunden** | **1 Stunde** |
| **Server Pod Age** | **5 Tage 1 Stunde** | **1 Stunde** |
| **Server Deployment** | `livekit-server-staging` | `livekit-server` |
| **Recording Status** | ✅ `14ddd793` completed (14:28 UTC) | ❌ `6b96c1af` failed (14:02 UTC) |
| **Helm Charts** | Nicht im Git-Repo | `livekit-server-1.9.0.tgz`, `egress-1.8.4.tgz` |
| **Deploy-Script** | `03-deploy-manifests.sh` (skip LiveKit) | `03-deploy-livekit.sh` (immer restart) |

### 5.2 WICHTIGSTER UNTERSCHIED: Egress Image Version

```
Staging:     livekit/egress:v1.8.4  ← KEIN Tag in Values → Chart-Default
Production:  livekit/egress:v1.14.1 ← EXPLIZIT in egress-values.yaml: tag: "v1.14.1"
```

**Das ist der wahrscheinlichste Root Cause.** Die Egress-Version v1.14.1 wurde am 20.08. in Production eingeführt (Commit `11fa7e7b`), aber NICHT in Staging.

### 5.3 Deploy-Strategie

**Staging:** LiveKit wird bei CI/CD-NIEMALS neu gestartet:
```bash
# scripts/deploy-staging/03-deploy-manifests.sh
[[ "$fname" == *livekit-*-deployment.yaml ]] && continue  # ← SKIP!
# Kein helm upgrade, kein rollout restart
```

**Production:** LiveKit wird bei JEDEM Deploy neu gestartet:
```bash
# scripts/deploy-prod/03-deploy-livekit.sh
helm upgrade --install livekit-server ...
kubectl rollout restart deployment/livekit-server  # ← IMMER!
helm upgrade --install livekit-egress ...
kubectl rollout restart deployment/livekit-egress  # ← IMMER!
```

### 5.4 Hypothesen (nach Staging-Vergleich)

| # | Hypothese | Wahrscheinlichkeit | Beweis |
|---|-----------|-------------------|--------|
| **H1** | **Egress v1.14.1 hat ICE-Regression** (WebRTC-Verbindung scheitert nach Pod-Restart) | 🔴 HOCH | Staging v1.8.4 funktioniert, Production v1.14.1 nicht |
| **H2** | **Frischer Pod hat ICE-Timing-Problem** (Startup-Phase, CPU-Last, Network-Init) | 🟡 MITTEL | Production-Pods sind 1h alt, Staging-Pods 3-5 Tage |
| **H3** | **CPU-Last 85% verursacht ICE-Timeout** (Production: 85%, Staging: wahrscheinlich weniger) | 🟡 MITTEL | ICE-Timeout 4.5s = knapp unter 5s ConnectTimeout |
| **H4** | **Helm-Rollback ändert Secret-Inhalt** (`helm upgrade --install` könnte Secret neu rendern) | 🟢 NIEDRIG | ConfigMaps identisch, aber Secret-Inhalt unbekannt |

---

## 6. Offene Fragen (aktualisiert)

| # | Frage | Warum wichtig |
|---|-------|---------------|
| 1 | **Warum scheitert ICE nach Pod-Restart, aber nicht nach 36h Laufzeit?** | Hauptfrage — observables Symptom |
| 2 | **Was steht im `EGRESS_CONFIG_BODY` Secret?** | Secret-Inhalt unbekannt — könnte `ws_url` oder Keys fehlen |
| 3 | **Ist es ein CPU-Last-Problem?** (k3s bei 85% → ICE-Timing scheitert) | Könnte erklärt warum intermittierend |
| 4 | **Ist es ein Redis-State-Problem?** (frischer Pod + alter Redis-State) | Könnte durch Pod-Restart verursacht sein |
| 5 | **Hat `helm upgrade --install` das Secret geändert?** | Secret-Inhalt könnte sich geändert haben |
| 6 | **Funktioniert ein zweiter Test-JETZT?** (Pods sind jetzt 1h alt) | Reproduzierbarkeit prüfen |
| 7 | **Warum gibt Stop-Recording keinen Fehler zurück?** | Frontend-UX-Problem |

---

## 7. Dokumentierte Infrastruktur

### 6.1 LiveKit Server

```
Helm Chart:  livekit-server-1.9.0.tgz
Image:       livekit/livekit-server:v1.9.0
hostNetwork: true
Ports:       7880 (HTTP), 7881 (TCP), 3478 (TURN), 50000-60000 (WebRTC UDP)
Config:      rtc.allow_tcp_fallback=true, rtc.use_external_ip=true
Resources:   500m-1000m CPU, 512Mi-1024Mi Memory
```

### 6.2 LiveKit Egress

```
Helm Chart:  egress-1.8.4.tgz
Image:       livekit/egress:v1.14.1
hostNetwork: true
ws_url:      ws://livekit-server:7880
Config:      EGRESS_CONFIG_BODY (Secret, Helm-generiert)
Resources:   500m-2 CPU, 512Mi-2Gi Memory
```

### 6.3 Deploy-Script (03-deploy-livekit.sh)

```bash
# Schritt 1: Helm Upgrade (gleiche Values = kein Config-Unterschied)
helm upgrade --install livekit-server ...
helm upgrade --install livekit-egress ...

# Schritt 2: hostNetwork Patches (immer, auch wenn schon gesetzt)
kubectl patch deployment livekit-server --type='json' -p='[{hostNetwork: true}]'
kubectl patch deployment livekit-egress --type='json' -p='[{hostNetwork: true}]'

# Schritt 3: Rollout Restart (JEDES MAL — unabhängig von Config-Änderungen!)
kubectl rollout restart deployment/livekit-server
kubectl rollout restart deployment/livekit-egress
```

**⚠️ Kritischer Punkt:** `kubectl rollout restart` wird IMMER ausgeführt — auch wenn sich nichts geändert hat. Das ist die Ursache für den Pod-Restart.

### 6.4 Pipeline-Flow

```
User startet Meeting
  → Backend: CreateRoom (LiveKit API)
  → LiveKit Server: Room erstellt (WebSocket)
  → User betritt Room
  → Backend: StartRoomCompositeEgress (LiveKit API)
  → LiveKit Server: Egress gestartet (Webhook: egress_started)
  → LiveKit Egress: Verbindet zu Server (WebSocket + WebRTC)
  → LiveKit Egress: Nimmt Audio auf
  → LiveKit Egress: Speichert in MinIO (S3)
  → Backend: Webhook egress_ended
  → Backend: Startet Celery Task (process_recording)
  → Celery Worker: Pipeline (S3 → Gladia → Speaker ID → Sentinel → Mistral PV → DB)
```

**Fehlerpunkt:** LiveKit Egress → WebRTC Verbindung zum Server (Schritt 7)

---

## 8. Vorgeschlagener Plan (keine Änderungen)

### Sofort (P0)

1. **EGRESS_CONFIG_BODY Secret prüfen**
   - `kubectl get secret -n meeting-automation -l app.kubernetes.io/name=livekit-egress -o yaml`
   - Inhalt mit ConfigMap `livekit-egress` vergleichen
   - Prüfen ob `ws_url`, `api_key`, `api_secret` korrekt sind

2. **Zweiten Test starten** (Pods sind jetzt ~1h alt)
   - Prüfen ob Fehler reproduzierbar ist
   - Wenn JA → Pod-Alter ist nicht der Faktor
   - Wenn NEIN → Pod-Alter / Startup-Timing ist relevant

3. **Egress Startup-Logs abfangen**
   - Egress pod löschen, neuen starten
   - `kubectl logs -f` beim Starten — alle Logs bis zum ersten Egress-Request

### Kurzfristig (P1)

4. **Deploy-Script optimieren**
   - `kubectl rollout restart` nur bei Config-Änderungen ausführen
   - Nicht bei jedem Deploy — verhindert unnötige Pod-Restarts

5. **Egress CPU-Ressource prüfen**
   - `cpu_cost.room_composite_cpu_cost: 2.0` → Egress braucht 2 Cores für Room-Composite
   - Bei k3s 85% CPU → könnte ICE-Timing scheitern

### Mittelfristig (P2)

6. **LiveKit Version vergleichen**
   - Server v1.9.0, Egress v1.14.1 — Version-Mismatch?
   - Prüfen ob kompatible Versionen

7. **Egress ConfigMap-Bereinigung**
   - `livekit-egress-config` (manuell, 20.08.) — wird NICHT genutzt
   - Enthält `room_composite_cpu_cost: 1.5` vs Helm `2.0`
   - Verwirrend — löschen oder mit Helm synchronisieren

---

## 9. Betroffene Systeme

| System | Auswirkung |
|--------|-----------|
| **Recording** | 🔴 Komplett funktionsunfähig |
| **Stop-Recording** | 🔴 Kein Recording zum Stoppen |
| **Pipeline (TIMING-Logs)** | 🔴 Kein Recording → keine Pipeline → keine Logs |
| **Transcription** | 🔴 Kein Recording → keine Transcription |
| **PV-Generierung** | 🔴 Kein Recording → keine PV |
| **LiveKit Server** | ✅ Funktioniert (Room, Participant, WebRTC) |
| **Celery Worker** | ✅ Funktioniert (keine Tasks zum Verarbeiten) |
| **Backend API** | ✅ Funktioniert (Stop-Recording antwortet) |
| **Database** | ✅ Funktioniert |
| **MinIO** | ✅ Funktioniert |

---

## 10. Metriken

| Metrik | Wert |
|--------|------|
| Letzte erfolgreiche Recording | `7cc15aba` (22.08. 20:52 UTC) |
| Letzte fehlgeschlagene Recording | `6b96c1af` (23.08. 14:02 UTC) |
| Egress Failures (heute) | 1 |
| Server Restarts (heute) | 1 (13:12 UTC) |
| Egress Restarts (heute) | 1 (13:12 UTC) |
| k3s CPU (bei Fehler) | 85% |
| k3s Load (bei Fehler) | 10.90 (136% auf 8 Cores) |

---

## 11. Änderungshistorie

| Datum | Änderung | Autor |
|-------|----------|-------|
| 2026-08-23 | Incident erstellt | Buffy (Freebuff) |
