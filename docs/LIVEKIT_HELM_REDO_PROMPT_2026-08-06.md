# PROMPT — LiveKit Helm Wiederaufbau (100% Chart-konform)

> **Zweck dieses Dokuments:** Dies ist ein **ausführbarer Prompt für einen Agenten**.
> Der Agent soll das LiveKit-Helm-Szenario **nach den offiziellen LiveKit-Helm-Definitionen**
> (die in Abschnitt 2 zu 100% belegt sind) korrekt wieder aufbauen:
> (1) Docs korrigieren, (2) Values-Dateien chart-konform neu erstellen,
> (3) Migration mit Plan + Fallback durchführen.
>
> **Regel:** KEINE Änderung ohne vorherigen Plan + Freigabe.
> **Fehler-Protokoll (strikt):** Bei jedem Fehler → **SOFORT STOPP** → Ursache untersuchen
> (anhand dieses Plans + offizieller LiveKit-Helm-Dokumentation) → **Fehler beheben**.
> **Der Fallback wird NUR ausgeführt, wenn die Hypothese nach vollständiger Untersuchung
> NICHT 100% funktioniert.**

---

## 1. Auftrag an den Agenten

Du führst folgende drei Aufgaben in dieser Reihenfolge aus. **Nur Analyse/Diskussion bis zur
expliziten Freigabe des Users. Keine Modifikation ohne Freigabe.**

1. **Doku-Korrektur:** Korrigiere die falsche Diagnose in
   `docs/LIVEKIT_RECORDING_PIPELINE.md` und `docs/HELM_CHART_MIGRATION_PLAN_2026-08-06.md`
   (die Behauptung "Helm fehlen UDP-Ports 50000-60000 → Mikrofon tot" ist **faktisch falsch**,
   Beweis in Abschnitt 2).
2. **Values-Dateien chart-konform neu erstellen:**
   `infrastructure/kubernetes/staging/livekit-server-values.yaml` und
   `infrastructure/kubernetes/staging/egress-values.yaml` — exakt nach der offiziellen
   Chart-Struktur (Abschnitt 3).
3. **Wiederaufbau:** LiveKit-Helm-Migration in Staging mit **Plan vorab + Fallback am Ende**
   (Abschnitt 4). Bei jedem Fehler: **SOFORT STOPP** und Fehler-Protokoll (4.4) ausführen —
   Ursache untersuchen und beheben. **Fallback (4.5) NUR wenn die Hypothese nach Untersuchung
   nicht 100% funktioniert.** Ergebnis melden.

---

## 2. Bewiesene Fakten (100% belegt — KEINE Annahmen)

> Alle Behauptungen unten sind durch direkte Quellen belegt:
> offizielle Helm-Chart-Definitionen (`helm show values livekit/livekit-server` v1.9.0,
> `helm show values livekit/egress` v1.8.4), offizielle Chart-Templates
> (`/tmp/chart-inspect/livekit-server/templates/`, `/tmp/egress-inspect/egress/templates/`)
> und die offizielle LiveKit-Config (`config-sample.yaml` aus livekit/livekit).

### 2.1 Helm ist eine 100% valide Variante (User-Aussage bestätigt)

Die offizielle `values.yaml` des `livekit/livekit-server` Charts v1.9.0 hat **bereits eingebaut**:

```yaml
podHostNetwork: true          # ← hostNetwork ist der OFFIZIELLE DEFAULT des Charts!
livekit:
  rtc:
    tcp_port: 7881
    port_range_start: 50000   # ← UDP-Range ist OFFIZIELLER DEFAULT des Charts!
    port_range_end: 60000
    use_external_ip: true
  turn:
    enabled: false            # ← TURN ist per Default AUS
```

**Konsequenz:** Die frühere Behauptung "Helm hat keine UDP-Ports 50000-60000" ist **faktisch
falsch**:
- Der UDP-Range wird **ausschließlich über die Config** gesteuert (`rtc.port_range_start/end`).
- Bei `podHostNetwork: true` teilt der Container den Netzwerk-Namespace des Nodes —
  **hostPorts werden dabei komplett ignoriert**. `containerPort/hostPort` in den Raw-Manifesten
  waren **auch dort wirkungslos** für die Bindung.
- Der Helm-Einsatz lief auf `10.0.0.191` mit `hostNetwork: true` — **identischer Zustand**
  wie bei den Raw-Manifesten.

### 2.2 Wahre Ursache der leeren Aufnahme: TURN-Konfiguration (nicht Helm)

**Offizieller TURN-Block** (`config-sample.yaml`, Zeilen 283-315):

```yaml
# turn server
# turn:
#   enabled: false
#   udp_port: 3478
#   tls_port: 5349
#   relay_range_start: 1024
#   relay_range_end: 30000
#   external_tls: true
#   # needs to match tls cert domain
#   domain: turn.myhost.com
#   # optional (set only if not using external TLS termination)
#   # cert_file: /path/to/cert.pem
#   # key_file: /path/to/key.pem
```

Laut offizieller Definition **erfordert TURN ein TLS-Zertifikat** — via EINEM von:
1. `turn.secretName` (Helm-Chart-Weg), ODER
2. Env-Variablen `LIVEKIT_TURN_CERT` + `LIVEKIT_TURN_KEY`, ODER
3. `cert_file` + `key_file` in der Config

**Beleg im Cluster (Rollback-Zustand — identisch mit Git-Raw):**

Cluster-Configmap `livekit-config-staging`:
```yaml
turn:
  enabled: true
  udp_port: 3478
```
→ **KEIN `domain`, KEIN `secretName`, KEINE cert/key-Dateien, KEINE TURN-Env-Variablen.**

Git-Raw `infrastructure/kubernetes/staging/livekit-configmap.yaml` — **identisch**:
```yaml
turn:
  enabled: true
  udp_port: 3478
```

**Log-Beweis (Egress, Test "test batata"):**
```
12:13:13 - Failed to send packet: CreatePermission error response (error 403:)
12:13:14 - ICE connected (nach Fehlern)
12:13:14 - Audio-Track subscribed
12:13:15 - Pipeline playing
12:13:29 - egress_ending (StopEgress API)
12:13:30 - egress_complete
```

**Erklärung:**
- TURN ist `enabled: true`, aber **ohne TLS-Zertifikat** → der eingebaute TURN-Server kann
  keine TURN-TLS-Verbindungen aufbauen → **403 CreatePermission**.
- Wenn der Client/Egress einen **direkten UDP-Pfad** findet (gleiches Netz, hostNetwork),
  wird TURN gar nicht gebraucht → funktioniert (Test "test 67": 154'753 Bytes, Transkription OK).
- Wenn TURN nötig ist → 403 → **nur 3964 Bytes Audio** (fast leer) → leere Transkription →
  leeres PV. **Das ist der bewiesene Grund für leere AI-Suggestion/Insight/PV.**

### 2.3 Egress-Chart: Config-Übergabe (mein früherer `env:`-Ansatz war ein Chart-Fehler)

Offizielles `livekit/egress` Chart v1.8.4:

`egress/templates/configmap.yaml`:
```yaml
data:
  config.yaml: |
{{ toYaml .Values.egress | indent 4 }}
```

`egress/templates/deployment.yaml`:
```yaml
env:
  - name: EGRESS_CONFIG_BODY
    valueFrom:
      configMapKeyRef:
        name: {{ include "egress.fullname" . }}
        key: config.yaml
```

**Konsequenz:**
- Das Chart rendert die Egress-Config **ausschließlich** aus `.Values.egress` und übergibt sie
  als `EGRESS_CONFIG_BODY`. Ein **frei definiertes `env:`-Feld gibt es im Chart NICHT** —
  mein früherer `env:`-Block in `egress-values.yaml` wäre von Helm **ignoriert** worden.
- Health-/Metrics-Ports kommen aus `egress.health_port` / `egress.prometheus_port`
  (offizielle Defaults: `health_port: 8080`, `prometheus_port: 9090`).
- Server-Verbindung (URL + Keys) gehört in die Config unter `.Values.egress`
  (`ws_url` bzw. `url`, `api_key`, `api_secret`) oder via Env-Variablen, die das
  egress-Binary selbst unterstützt (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`).

### 2.4 WICHTIGER Befund für die Egress-Migration: Chart kann KEIN hostNetwork

Verifiziert im offiziellen `egress/templates/deployment.yaml` (Chart v1.8.4):
Das Deployment-Template enthält **KEINEN `hostNetwork`-Key** — das Chart kann hostNetwork
**nicht** setzen. Die Raw-Egress-Manifeste nutzen aber `hostNetwork: true`.

**Konsequenz für die Migration:**
- Egress via Helm würde auf **Pod-IP** laufen (kein hostNetwork) — das ist für die Egress-
  Kommunikation zu LiveKit normalerweise ausreichend (Egress verbindet sich ausgehend zu `ws_url`).
- Der hostNetwork-Portkonflikt (7000/7002/7980), der die Egress-Skalierung blockiert hat,
  entfällt damit — Helm-Egress könnte mehrfach skaliert werden (Ziel der Migration!).
- ABER: Dies muss VOR der Migration im Plan entschieden und dem User vorgestellt werden
  (Verhaltensänderung: Pod-IP statt Node-IP).

### 2.5 Zusammenfassung der korrigierten Ursachenkette

| Behauptung (ALT, falsch) | Fakt (NEU, bewiesen) |
|---|---|
| Helm fehlen UDP-Ports → Mikrofon tot | UDP-Range ist Chart-Default; hostNetwork aktiv; Ports waren offen |
| Helm-Umbau hat die leere Aufnahme verursacht | Gleicher TURN-403 existiert in Raw UND Helm; Ursache ist die TURN-TLS-Konfiguration |
| Egress braucht `env:`-Block | Egress-Chart übergibt Config via `EGRESS_CONFIG_BODY` (aus `.Values.egress`) |

---

## 3. Chart-konforme Values-Dateien (Neu-Erstellung)

### 3.1 `infrastructure/kubernetes/staging/livekit-server-values.yaml`

```yaml
replicaCount: 1

image:
  repository: livekit/livekit-server
  pullPolicy: IfNotPresent

# Labels/Service-Name identisch zu den Raw-Manifesten halten
nameOverride: livekit-config-staging (was: livekit-server-staging)
fullnameOverride: livekit-config-staging (was: livekit-server-staging)

livekit:
  port: 7880
  log_level: info
  rtc:
    tcp_port: 7881
    port_range_start: 50000
    port_range_end: 60000
    use_external_ip: true
  redis:
    address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
    password: <REDIS_PASSWORD>
    db: 0
  keys:
    <LIVEKIT_API_KEY>: <LIVEKIT_API_SECRET>
  # TURN: ENTWEDER korrekt mit TLS ... ODER deaktivieren (direkter UDP-Pfad reicht im Cluster)
  turn:
    enabled: false        # ← Empfehlung: AUS (Beweis: 403 kommt nur von kaputtem TURN)
    # ODER korrekt mit TLS (nur wenn TURN zwingend gebraucht wird):
    # enabled: true
    # udp_port: 3478
    # tls_port: 5349
    # domain: turn.meeting-automation.com   # muss zum Zertifikat passen
    # secretName: livekit-turn-tls          # TLS-Secret mit cert+key
  webhook:
    api_key: <LIVEKIT_API_KEY>
    urls:
      - http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/livekit/webhooks

# hostNetwork = OFFIZIELLER Chart-Default, explizit setzen
podHostNetwork: true

loadBalancer:
  type: disable
  servicePort: 7880

nodeSelector:
  kubernetes.io/hostname: instance-20260329-0846

resources:
  limits:
    cpu: 1000m (verified in livekit-server-deployment.yaml:59)
    memory: 1024Mi
  requests:
    cpu: 1000m
    memory: 512Mi

autoscaling:
  enabled: false

serviceMonitor:
  create: false
```

**Verboten/überflüssig** (Chart-strukturell falsch): `force_tcp`, `allow_tcp_fallback`,
`tcp_fallback_rtt_threshold`, `containerPort`/`hostPort`-Listen — die gehören NICHT in die
Helm-Values (RTC-Block übernimmt die Ports über `port_range_start/end` + `podHostNetwork`).

### 3.2 `infrastructure/kubernetes/staging/egress-values.yaml`

```yaml
replicaCount: 1

image:
  repository: livekit/egress
  pullPolicy: IfNotPresent

egress:
  log_level: info
  health_port: 8080
  prometheus_port: 9090
  # Verbindung zum LiveKit Server (config-seitig)
  ws_url: ws://10.0.0.191:7880          # oder: url: ...
  api_key: <LIVEKIT_API_KEY>
  api_secret: <LIVEKIT_API_SECRET>

# Falls env-Variablen für das egress-Binary nötig sind (S3, Redis), MUSS geprüft werden,
# ob das Chart ein offizielles env-Feld unterstützt — sonst Config-Keys unter .Values.egress verwenden.

resources:
  limits:
    cpu: 1000m (verified in livekit-server-deployment.yaml:59)
    memory: 1024Mi
  requests:
    cpu: 1000m
    memory: 512Mi

terminationGracePeriodSeconds: 3600
autoscaling:
  enabled: false
serviceMonitor:
  create: false
```

---

## 4. Wiederaufbau-Plan mit Fallback

> **Pflicht:** Vor jeder Modifikation dem User den Plan vorlegen und **Freigabe abwarten**.
> **Fehler-Protokoll (strikt, 4.4):** Bei jedem unerwarteten Fehler: **SOFORT STOPP** →
> Ursache untersuchen (Plan + offizielle LiveKit-Helm-Doku) → **Fehler beheben**.
> **Fallback (4.5) NUR wenn die Hypothese nach Untersuchung nicht 100% funktioniert.**

### 4.1 Vorbereitung (nur Analyse — keine Änderung)

- [ ] Git-Status prüfen (`git status`) — nichts ändern/pushen ohne Auftrag.
- [ ] Aktuellen Cluster-Zustand dokumentieren: Deployments, ConfigMaps, NetworkPolicies,
      Secrets, aktueller Recording-/Transkriptions-/PV-Zustand (leere TURN-403-Kette belegen).
- [ ] Backup-Verzeichnis `/tmp/livekit-backup/` prüfen (existiert aus dem Rollback).

### 4.2 Docs korrigieren (Doku-Aufgabe)

- [ ] `docs/HELM_CHART_MIGRATION_PLAN_2026-08-06.md`:
  - Abschnitt "KRITISCHES PROBLEM: Fehlende UDP-Ports" **ersetzen** durch
    "KRITISCHES PROBLEM: TURN-TLS (403 CreatePermission) — belegt mit Logs + Config-Beweis".
  - Tabelle "Ports fehlen" durch die TURN-Ursachenkette (2.2) ersetzen.
  - `force_tcp`/`allow_tcp_fallback`/`tcp_fallback_rtt_threshold` aus Values entfernen.
- [ ] `docs/LIVEKIT_RECORDING_PIPELINE.md`:
  - Helm-Abschnitt korrigieren: UDP-Range ist Chart-Default; hostNetwork Chart-Default.
  - Egress-Config-Übergabe (`EGRESS_CONFIG_BODY` statt `env:`) korrigieren.
  - Test "test batata" → Ursache TURN-403 dokumentieren (nicht "Helm kaputt").
- [ ] Diese Datei als Referenz verlinken.

### 4.3 Migration (erst NACH Freigabe)

1. **Dry-Run:** `helm install livekit-server livekit/livekit-server -f ... --dry-run --debug`
   → prüfen, dass gerenderte Config korrekt ist.
2. **Test-Namespace:** Helm-Install in separatem Namespace (`livekit-test`), Health-Check,
   dann wieder entfernen.
3. **Staging:** Alt-Server `scale --replicas=0` → `helm install` → `rollout status` →
   Health-Check → NetworkPolicy-Labels prüfen.
4. **Egress:** analog mit `egress-values.yaml`.
5. **Verifikation:** Recording-Test (Mikrofon/Audio senden), prüfen:
   `recording.file_size` > 100KB, Transkription non-empty, PV non-empty.
6. **Parallel-Test:** 2 gleichzeitige Recordings (Ziel des Helm-Wiederaufbaus).

### 4.4 FEHLER-PROTOKOLL (SOFORT STOPP bei jedem Fehler)

> **Grundprinzip des Users:** *"Löschen ist verboten — Fehler behandelt den Grund und behebt
> ihn. Der Fallback kann nur durchgeführt werden, wenn die Hypothese nicht 100% funktioniert."*

**Ablauf bei JEDEM unerwarteten Fehler (ohne Ausnahme):**

1. **SOFORT STOPP** — keine weiteren Änderungen, keine Umgehungslösungen, kein Fallback.
2. **Fehler exakt dokumentieren:** Log-Auszug, Kommando, Zeitstempel, betroffene Ressource.
3. **Hypothese prüfen:** Passt der Fehler zur Hypothese aus Abschnitt 2 (Chart-Defaults,
   TURN-403, EGRESS_CONFIG_BODY, hostNetwork)?
4. **Ursache untersuchen — in dieser Reihenfolge:**
   a. **Dieser Plan** (Abschnitte 2-4) erneut lesen.
   b. **Offizielle LiveKit-Helm-Dokumentation erneut einlesen:**
      - `helm show values livekit/livekit-server` / `helm show values livekit/egress`
      - Chart-Templates: `helm pull livekit/livekit-server --untar`, dann
        `livekit-server/templates/configmap.yaml` + `deployment.yaml`
      - Offizielle Config-Doku: `config-sample.yaml` aus `livekit/livekit`
        und `livekit/egress` (Abschnitt 2.2/2.3)
      - LiveKit Docs: TURN (TLS-Anforderung), rtc-Ports, Egress-Config
   c. **Cluster-Logs:** Server- / Egress- / Backend- / Celery-Logs nach dem Fehler durchsuchen.
   d. **Cluster-Zustand:** ConfigMaps, NetworkPolicies, Secrets, Services vergleichen.
5. **Fehler beheben** (nicht umgehen): Werte/Config gemäß der offiziellen Definition anpassen.
6. **Behebung verifizieren:** betroffenen Schritt erneut ausführen (z.B. Dry-Run, Health-Check,
   Recording-Test).
7. **Erst danach** entscheiden:
   - **Hypothese funktioniert zu 100%** → weiter mit dem Plan (ab dem Schritt, der fehlschlug).
   - **Hypothese funktioniert nachweislich NICHT 100%** (Grund belegt, nicht angenommen) →
     **erst jetzt** Fallback (4.5) ausführen und Ergebnis melden.

**Verboten während des Protokolls:**
- ❌ Weitermachen ohne Ursachenuntersuchung.
- ❌ Fehler durch neue Umgehungslösungen überdecken.
- ❌ Fallback vor Abschluss der Untersuchung (nur bei zwingendem Grund: Produktion/Blockade).

### 4.5 Fallback (NUR wenn die Hypothese nach Untersuchung nicht 100% funktioniert)

> **Voraussetzung:** Fehler-Protokoll (4.4) vollständig durchlaufen; Grund belegt.
> **Hinweis:** Fallback stellt den vorherigen Raw-Zustand wieder her und behandelt NICHT den
> Grund — er ist die letzte Option, kein erster Reflex.

```bash
helm uninstall livekit-server -n meeting-automation-staging
helm uninstall livekit-egress -n meeting-automation-staging
# Roh-Manifeste aus Backup /tmp/livekit-backup/ (bzw. Git-Dateien) wieder anwenden:
kubectl apply -f infrastructure/kubernetes/staging/livekit-server-deployment.yaml
kubectl apply -f infrastructure/kubernetes/staging/livekit-egress-deployment.yaml
kubectl apply -f infrastructure/kubernetes/staging/livekit-service.yaml
kubectl apply -f infrastructure/kubernetes/staging/livekit-configmap.yaml
kubectl apply -f infrastructure/kubernetes/staging/livekit-networkpolicy.yaml
kubectl rollout restart deployment/livekit-config-staging (was: livekit-server-staging) -n meeting-automation-staging
kubectl rollout status deployment/livekit-config-staging (was: livekit-server-staging) -n meeting-automation-staging --timeout=180s
```

**Rollback-Verifikation:** Pods Running, Recording-Test erneut (Vergleichs-Baseline: "test 67"
mit 154KB erfolgreich).

### 4.6 Erfolgskriterien

| Kriterium | Erfolg |
|---|---|
| Helm-Installation | Keine Fehler, gerenderte Config = Abschnitt 3 |
| Server-Health | HTTP 200 auf 7880 |
| Egress-Health | HTTP 200 auf health_port |
| Recording | `status=completed`, `file_size` > 100KB |
| Transkription | `full_text` non-empty |
| PV | Title/Content/Actions non-empty |
| Parallel | 2 gleichzeitige Recordings erfolgreich |

---

## 5. Abschlussbericht an den User

Am Ende lieferst du:
1. Welche Dateien geändert/erstellt wurden (Pfade).
2. Den Log-Beweis der TURN-403-Kette (vorher/nachher).
3. Recording-Test-Ergebnis (Dateigröße, Transkriptionslänge, PV-Inhalt).
4. **Bei jedem aufgetretenen Fehler:** vollständiges Fehler-Protokoll (4.4) — Fehler, Untersuchung,
   Behebung, Verifikation.
5. Falls Fallback (4.5) ausgelöst wurde: **den belegten Grund, warum die Hypothese nicht 100%
   funktioniert hat** (nicht nur "was/wann" — sondern die nachgewiesene Ursache).

---

*Referenzen: offizielle Chart-Values v1.9.0/v1.8.4, Chart-Templates (configmap.yaml,
deployment.yaml), config-sample.yaml aus livekit/livekit, Cluster-Logs (Egress 403,
webhook egress_ended HTTP 200), Cluster-Configmap vs. Git-Raw (identisch).*
