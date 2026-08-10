# LiveKit Helm Chart Migration Plan

## Status
- **Erstellt**: 2026-08-06
- **Phase**: Planung (KEINE Änderungen ohne Genehmigung!)
- **Ziel**: LiveKit von Raw Manifests zu Helm Chart migrieren

## Zusammenfassung

| Aspekt | Aktuell | Ziel |
|--------|---------|------|
| **Deployment** | Raw Manifests (kubectl apply) | Helm Chart |
| **Server** | livekit-config-staging (hostNetwork: true) | livekit/livekit-server Chart |
| **Egress** | livekit-egress-staging (hostNetwork: true) | livekit/egress Chart ⚠️ Chart kann KEIN hostNetwork setzen |
| **Skalierung** | 1 Pod pro Komponente | 2+ Pods (Autoscaling möglich) |
| **Wartung** | Manuell | Helm-managed |

---

## 1. FALSCHIRM-SZENARIEN (5 Szenarien)

### Szenario 1: Helm Chart Installation fehlgeschlagen
- **Symptom**: `helm install` fehlerhaft, Pods starten nicht
- **Ursache**: Falsche Werte, Image-Pull-Errors, RBAC-Probleme
- **Lösung**: `helm uninstall`, alte Manifests wiederherstellen
- **Risiko**: NIEDRIG (kein Datenverlust)

### Szenario 2: LiveKit Server erreicht Redis nicht
- **Symptom**: Server-Logs zeigen "connection refused" zu Redis
- **Ursache**: Falsche Redis-Adresse im Helm-Wert
- **Lösung**: Redis-Adresse in values.yaml korrigieren
- **Risiko**: NIEDRIG (einfach zu beheben)

### Szenario 3: Egress erreicht LiveKit Server nicht
- **Symptom**: Recording startet nicht, Egress-Logs zeigen Verbindungsfehler
- **Ursache**: Falsche WebSocket-URL, NetworkPolicy blockiert
- **Lösung**: `ws_url` in `.Values.egress` prüfen, NetworkPolicy anpassen
- **Risiko**: MITTEL (kann Production beeinflussen)

### Szenario 4: WebRTC Media funktioniert nicht
- **Symptom**: Recording-Qualität schlecht, Audio/Video desync
- **Ursache**: UDP-Ports (50000-60000) nicht erreichbar ODER TURN ohne TLS-Zertifikat (403 CreatePermission)
- **Lösung**: hostNetwork: true beibehalten, `rtc.port_range_start/end` in Config prüfen, TURN korrekt konfigurieren oder deaktivieren
- **Risiko**: HOCH (kann Recording unbrauchbar machen)

### Szenario 5: Helm Chart hat andere Labels als alte Manifests
- **Symptom**: Services finden Pods nicht, Endpoints leer
- **Ursache**: Helm-Chart verwendet andere Labels als manuelle Manifests
- **Lösung**: Labels in values.yaml anpassen
- **Risiko**: MITTEL (erfordert Labels-Analyse)

---

## 2. SCHRITT-FÜR-SCHRITT IMPLEMENTIERUNGSPLAN

> **Hinweis zu `**Rollback**:`-Zeilen:** Die per-Schritt-`**Rollback**:`-Einträge unten sind
> **reversible Undo-Optionen für den jeweiligen Schritt** (z.B. Test-Namespace löschen) —
> sie sind KEIN globaler Fallback. Bei einem echten Fehler gilt das strikte
> **Fehler-Protokoll** (Abschnitt 4): SOFORT STOPP → untersuchen → beheben →
> Fallback NUR wenn die Hypothese nicht 100% funktioniert.

### Phase 1: Vorbereitung (30 Minuten)

#### Schritt 1.1: Aktuellen Zustand sichern
```bash
# Backup aller LiveKit-Ressourcen
kubectl get deployment livekit-config-staging -o yaml > /tmp/livekit-server-backup.yaml
kubectl get deployment livekit-egress-staging -o yaml > /tmp/livekit-egress-backup.yaml
kubectl get service livekit-config-staging -o yaml > /tmp/livekit-service-backup.yaml
kubectl get configmap livekit-config-staging -o yaml > /tmp/livekit-config-backup.yaml
kubectl get configmap livekit-egress-config-staging -o yaml > /tmp/livekit-egress-config-backup.yaml
kubectl get networkpolicy livekit-policy -o yaml > /tmp/livekit-network-backup.yaml
kubectl get networkpolicy livekit-egress-policy -o yaml > /tmp/livekit-egress-network-backup.yaml
```

**Erfolgskriterium**: Alle Backup-Dateien vorhanden und nicht leer
**Rollback**: Backups verwenden um alten Zustand wiederherzustellen

#### Schritt 1.2: Helm Repository hinzufügen
```bash
helm repo add livekit https://helm.livekit.io
helm repo update
```

**Erfolgskriterium**: `helm search repo livekit` zeigt Charts an
**Rollback**: `helm repo remove livekit`

#### Schritt 1.3: Values.yaml für LiveKit Server erstellen
```yaml
# livekit-server-values.yaml
replicaCount: 1

image:
  repository: livekit/livekit-server
  pullPolicy: IfNotPresent

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
    password: redis_password
    db: 0
  keys:
    meeting-api-key: meeting-api-secret-2026-minimum-32-chars!
  turn:
    enabled: false  # TURN ohne TLS-Cert verursacht 403 CreatePermission → deaktivieren (direkter UDP reicht im Cluster)
    # ODER korrekt mit TLS-Zertifikat (nur wenn TURN zwingend gebraucht wird):
    # enabled: true
    # udp_port: 3478
    # tls_port: 5349
    # domain: turn.meeting-automation.com   # muss zum Zertifikat passen
    # secretName: livekit-turn-tls          # TLS-Secret mit cert+key
  webhook:
    api_key: meeting-api-key
    urls:
      - http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/livekit/webhooks

podHostNetwork: true  # BEIBEHALTEN für WebRTC UDP

nodeSelector:
  kubernetes.io/hostname: instance-20260329-0846

resources:
  limits:
    cpu: 1000m
    memory: 1024Mi
  requests:
    cpu: 1000m
    memory: 512Mi
```

**Erfolgskriterium**: Values.yaml valid mit `helm lint`
**Rollback**: Values.yaml löschen

### Phase 2: Test-Deployment (15 Minuten)

#### Schritt 2.1: Helm Dry-Run
```bash
helm install livekit-server-test livekit/livekit-server \
  -f livekit-server-values.yaml \
  --dry-run \
  --debug \
  -n meeting-automation-staging
```

**Erfolgskriterium**: Keine Fehler im Dry-Run
**Rollback**: Nichts (nur Test)

#### Schritt 2.2: Test-Namespace erstellen
```bash
kubectl create namespace livekit-test
```

**Erfolgskriterium**: Namespace erstellt
**Rollback**: `kubectl delete namespace livekit-test`

#### Schritt 2.3: Helm Chart in Test-Namespace installieren
```bash
helm install livekit-server-test livekit/livekit-server \
  -f livekit-server-values.yaml \
  -n livekit-test
```

**Erfolgskriterium**: Pods starten in Test-Namespace
**Rollback**: `helm uninstall livekit-server-test -n livekit-test`

#### Schritt 2.4: Test-Deployment verifizieren
```bash
# Pods prüfen
kubectl get pods -n livekit-test

# Logs prüfen
kubectl logs -n livekit-test deployment/livekit-server-test

# Service prüfen
kubectl get service -n livekit-test
```

**Erfolgskriterium**: Pods Running, keine Errors in Logs
**Rollback**: Test-Deployment löschen

### Phase 3: Migration (30 Minuten)

#### Schritt 3.1: LiveKit Server migrieren
```bash
# Alten Server stoppen
kubectl scale deployment livekit-config-staging --replicas=0

# Neuen Server starten
helm install livekit-server livekit/livekit-server \
  -f livekit-server-values.yaml \
  -n meeting-automation-staging
```

**Erfolgskriterium**: Neuer Server läuft, alter Server gestoppt
**Rollback**: Helm uninstall, alten Server wieder auf 1 Scale

#### Schritt 3.2: Service updaten
```bash
# Alten Service löschen
kubectl delete service livekit-config-staging

# Helm-Service verwenden (automatisch erstellt)
# ODER alten Service beibehalten wenn Labels nicht matchen
```

**Erfolgskriterium**: Service erreichbar
**Rollback**: Alten Service wieder erstellen

#### Schritt 3.3: NetworkPolicy anpassen
```yaml
# Aktualisierte NetworkPolicy für Helm-Chart-Labels
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: livekit-policy-helm
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: livekit-config-staging  # Helm-Label (nameOverride!)
  ingress:
  - ports:
    - port: 7880
    - port: 7881
  egress:
  - ports:
    - port: 6379
    - port: 7880
    - port: 7881
    - port: 3478
```

**Erfolgskriterium**: NetworkPolicy erlaubt Traffic
**Rollback**: Alte NetworkPolicy wiederherstellen

### Phase 4: Egress Migration (20 Minuten)

#### Schritt 4.1: Values.yaml für Egress erstellen
```yaml
# egress-values.yaml
replicaCount: 1

image:
  repository: livekit/egress
  pullPolicy: IfNotPresent

egress:
  log_level: debug
  insecure: true
  ws_url: ws://livekit-config-staging:7880
  api_key: meeting-api-key
  api_secret: meeting-api-secret-2026-minimum-32-chars!
  redis:
    address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
    password: redis_password
    db: 0
  s3:
    access_key: minio_user
    secret: minio_password
    endpoint: http://minio-staging:9000
    bucket: meeting-recordings-staging
    region: us-east-1
    force_path_style: true
  health_port: 7000
  template_port: 7980
  prometheus_port: 7002
  cpu_cost:
    room_composite_cpu_cost: 1.5
    web_cpu_cost: 1.5
    track_composite_cpu_cost: 1.0
    track_cpu_cost: 0.5

# HINWEIS: Das egress-Chart uebergibt die Config AUSSCHLIESSLICH ueber
# `EGRESS_CONFIG_BODY` (aus `toYaml .Values.egress`). Ein freies `env:`-Feld
# gibt es im Chart NICHT — alle Settings gehoeren unter `.Values.egress`.

resources:
  limits:
    cpu: 1000m
    memory: 1024Mi
  requests:
    cpu: 1000m
    memory: 512Mi
```

#### Schritt 4.2: Egress migrieren
```bash
# Alten Egress stoppen
kubectl scale deployment livekit-egress-staging --replicas=0

# Neuen Egress starten
helm install livekit-egress livekit/egress \
  -f egress-values.yaml \
  -n meeting-automation-staging
```

**Erfolgskriterium**: Neuer Egress läuft, alter Egress gestoppt
**Rollback**: Helm uninstall, alten Egress wieder auf 1 Scale

### Phase 5: Verifikation (15 Minuten)

#### Schritt 5.1: Health Check
```bash
# Server Health
kubectl exec -n meeting-automation-staging <server-pod> -- curl -s http://localhost:7880

# Egress Health
kubectl exec -n meeting-automation-staging <egress-pod> -- curl -s http://localhost:7000/health
```

**Erfolgskriterium**: Beide Health Checks OK

#### Schritt 5.2: Recording Test
```bash
# Meeting erstellen
# Recording starten
# Audio senden
# Recording stoppen
# Pipeline verifizieren
```

**Erfolgskriterium**: Recording funktioniert, Pipeline wird getriggert

#### Schritt 5.3: Multi-Recording Test
```bash
# 2 Meetings gleichzeitig erstellen
# Beide Recordings starten
# Prüfen ob beide funktionieren
```

**Erfolgskriterium**: Beide Recordings funktionieren parallel

---

## 3. ERFOLGSKRITERIEN (Gesamt)

| Kriterium | Erfolg | Misserfolg |
|-----------|--------|------------|
| **Helm Installation** | Keine Fehler | Pods starten nicht |
| **Server Health** | HTTP 200 | Timeout/Error |
| **Egress Health** | HTTP 200 | Timeout/Error |
| **Recording** | status=completed | status=failed/streaming |
| **Pipeline** | Transkription + PV | Keine Transkription |
| **Parallel** | 2 Recordings gleichzeitig | Nur 1 Recording |
| **Performance** | ≤90s End-to-End | >90s |

---

## 4. ROLLBACK-PLAN

### Rollback (NUR wenn die Hypothese nach Untersuchung nicht 100% funktioniert)

> **Fehler-Protokoll (strikt):** Bei jedem Fehler → **SOFORT STOPP** → Ursache untersuchen
> (anhand dieses Plans + offizieller LiveKit-Helm-Dokumentation) → **Fehler beheben**.
> Der Rollback ist die LETZTE Option und wird NUR ausgeführt, wenn die Hypothese nach
> vollständiger Untersuchung nicht 100% funktioniert (Prinzip: "Löschen ist verboten —
> Fehler behandelt den Grund und behebt ihn").
> **Detailprotokoll:** `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` Abschnitt 4.4.

```bash
# 1. Helm-Installationen entfernen
helm uninstall livekit-server -n meeting-automation-staging
helm uninstall livekit-egress -n meeting-automation-staging

# 2. Alte Manifests wiederherstellen
kubectl apply -f /tmp/livekit-server-backup.yaml
kubectl apply -f /tmp/livekit-egress-backup.yaml
kubectl apply -f /tmp/livekit-service-backup.yaml
kubectl apply -f /tmp/livekit-config-backup.yaml
kubectl apply -f /tmp/livekit-egress-config-backup.yaml
kubectl apply -f /tmp/livekit-network-backup.yaml
kubectl apply -f /tmp/livekit-egress-network-backup.yaml

# 3. Pods starten
kubectl scale deployment livekit-config-staging --replicas=1
kubectl scale deployment livekit-egress-staging --replicas=1

# 4. Verifizieren
kubectl get pods -l app=livekit-config-staging
kubectl get pods -l app=livekit-egress-staging
```

### Rollback-Zeitpunkt
- **Phase 1-2**: Kein Rollback nötig (nur Vorbereitung)
- **Phase 3**: Rollback nur nach Fehler-Protokoll, wenn Hypothese nicht 100% (innerhalb von 5 Minuten)
- **Phase 4**: Rollback nur nach Fehler-Protokoll, wenn Hypothese nicht 100% (innerhalb von 5 Minuten)
- **Phase 5**: Rollback nur mit Datenverlust (Recording im Gange) — vermeiden, erst beheben

---

## 5. CI/CD INTEGRATION

### GitHub Actions Workflow
```yaml
# .github/workflows/livekit-helm-migration.yml
name: LiveKit Helm Migration

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Helm
        uses: azure/setup-helm@v3
        with:
          version: 'v3.14.0'

      - name: Configure kubeconfig
        run: |
          if [ "${{ github.event.inputs.environment }}" == "staging" ]; then
            echo "${{ secrets.STAGING_KUBECONFIG }}" > /tmp/kubeconfig
          else
            echo "${{ secrets.PRODUCTION_KUBECONFIG }}" > /tmp/kubeconfig
          fi
          export KUBECONFIG=/tmp/kubeconfig

      - name: Backup current deployment
        run: |
          kubectl get deployment livekit-config-staging -o yaml > /tmp/livekit-server-backup.yaml
          kubectl get deployment livekit-egress-staging -o yaml > /tmp/livekit-egress-backup.yaml

      - name: Install Helm chart
        run: |
          helm repo add livekit https://helm.livekit.io
          helm repo update
          helm upgrade --install livekit-server livekit/livekit-server \
            -f infrastructure/kubernetes/staging/livekit-server-values.yaml \
            -n meeting-automation-staging

      - name: Verify deployment
        run: |
          kubectl rollout status deployment/livekit-server -n meeting-automation-staging --timeout=180s

      - name: Rollback on failure
        if: failure()
        run: |
          helm uninstall livekit-server -n meeting-automation-staging
          kubectl apply -f /tmp/livekit-server-backup.yaml
```

---

## 6. ZEITPLAN

| Phase | Dauer | Abhängigkeit |
|-------|-------|--------------|
| Phase 1: Vorbereitung | 30min | Keine |
| Phase 2: Test-Deployment | 15min | Phase 1 |
| Phase 3: Migration | 30min | Phase 2 |
| Phase 4: Egress Migration | 20min | Phase 3 |
| Phase 5: Verifikation | 15min | Phase 4 |
| **Gesamt** | **~2 Stunden** | |

---

## 7. RISIKO-ANALYSE

| Risiko | Wahrscheinlichkeit | Auswirkung | Minderung |
|--------|-------------------|------------|-----------|
| Helm Chart hat andere Labels | MITTEL | Services finden Pods nicht | Labels in values.yaml anpassen |
| WebRTC UDP funktioniert nicht | NIEDRIG | Recording qualität schlecht | hostNetwork: true beibehalten |
| Redis-Verbindung fehlgeschlagen | NIEDRIG | Server startet nicht | Redis-Adresse prüfen |
| Egress kann Server nicht erreichen | MITTEL | Recording funktioniert nicht | `ws_url` in `.Values.egress` prüfen |
| Performance-Regression | NIEDRIG | Recording langsamer | Benchmark durchführen |

---

## 8. NÄCHSTE SCHRITTE

1. **User-Genehmigung** für diesen Plan
2. **Backup** durchführen
3. **Test-Deployment** in separatem Namespace
4. **Migration** in Staging
5. **Verifikation** mit Recording-Test
6. **Production** nach erfolgreicher Staging-Migration

---

## 9. ÄNDERUNGSDOKUMENTATION

| Datum | Änderung | Verantwortlich |
|-------|----------|---------------|
| 2026-08-06 | Plan erstellt | Buffy |

---

**STATUS**: ⏸️ MIGRATION ROLLED BACK (2026-08-06) — Wiederaufbau geplant
**DATUM**: 2026-08-06
**DURCHGEFUEHRT VON**: Buffy

> **Korrektur:** Die Migration wurde nach Analyse der offiziellen Chart-Definitionen
> zurueckgesetzt (Rollback auf Raw-Manifeste). Die Diagnose "fehlende UDP-Ports" war falsch —
> siehe Abschnitt "KORRIGIERTE ANALYSE". Der Wiederaufbau erfolgt laut
> `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` nach erneuter Freigabe.

## ERGEBNIS DER MIGRATION

### Was passiert ist
| Schritt | Ergebnis | Dauer |
|---------|----------|-------|
| Backup | ✅ Erfolgreich | 30s |
| Helm Repo | ✅ livekit hinzugefuegt | 5s |
| Values.yaml | ✅ 3 Fixes noetig | 10min |
| Dry-Run | ✅ Keine Fehler | 5s |
| NetworkPolicy | ✅ Neue Labels unterstuetzt | 10s |
| Alten Server loeschen | ✅ Erfolgreich | 15s |
| Helm Install | ✅ Erfolgreich | 30s |
| Verifikation | ✅ Alles OK | 30s |
| **Gesamt** | **Erfolgreich** | **~15min** |

### Gefundene und behoebte Probleme
| Problem | Loesung |
|---------|--------|
| Service Port 80 statt 7880 | `loadBalancer.servicePort: 7880` |
| Labels `livekit-server` statt `livekit-config-staging` | `nameOverride: livekit-config-staging` |
| Service Name `livekit-server` statt `livekit-config-staging` | `fullnameOverride: livekit-config-staging` |
| NetworkPolicy passte nicht zu Helm Labels | NetworkPolicy mit neuen Labels aktualisiert |
| Deployment selector immutable | Altes Release loeschen + neu installieren |

### KORRIGIERTE ANALYSE (2026-08-06): Wahre Ursache = TURN-TLS, NICHT fehlende UDP-Ports

> **WICHTIG:** Die fruehere Behauptung "Helm fehlen UDP-Ports 50000-60000" ist **faktisch falsch**
> und wurde nach Analyse der offiziellen Chart-Definitionen korrigiert (100% belegt).

#### 1. Helm hat die UDP-Ports — Chart-Defaults beweisen es

Offizielle `values.yaml` des `livekit/livekit-server` Charts v1.9.0 (`helm show values livekit/livekit-server`):

```yaml
podHostNetwork: true          # ← hostNetwork ist der OFFIZIELLE DEFAULT des Charts!
livekit:
  rtc:
    tcp_port: 7881
    port_range_start: 50000   # ← UDP-Range ist OFFIZIELLER DEFAULT des Charts!
    port_range_end: 60000
    use_external_ip: true
  turn:
    enabled: false            # ← TURN per Default AUS
```

**Konsequenz:**
- Der UDP-Range wird **ausschliesslich ueber die Config** gesteuert (`rtc.port_range_start/end`) — die waren in den Helm-Values vorhanden.
- Bei `podHostNetwork: true` teilt der Container den Netzwerk-Namespace des Nodes — **hostPorts werden dabei komplett ignoriert** (redundant). Die `containerPort 50000 + hostPort 50000` in den Raw-Manifesten waren **auch dort wirkungslos** fuer die Bindung.
- Der Helm-Server lief auf `10.0.0.191` mit `hostNetwork: true` — **identischer Zustand** wie bei den Raw-Manifesten.

#### 2. Wahre Ursache der leeren Aufnahme: TURN ohne TLS-Zertifikat

**Cluster-Configmap UND Git-Raw sind identisch** (Turn-Block ohne TLS):

```yaml
turn:
  enabled: true
  udp_port: 3478
```
→ **KEIN `domain`, KEIN `secretName`, KEINE `cert_file`/`key_file`, KEINE `LIVEKIT_TURN_CERT`/`LIVEKIT_TURN_KEY`**

**Offizielle LiveKit-Definition** (`config-sample.yaml`, Zeilen 283-315): TURN erfordert ein TLS-Zertifikat via EINEM von:
1. `turn.secretName` (Helm-Chart-Weg), ODER
2. Env-Variablen `LIVEKIT_TURN_CERT` + `LIVEKIT_TURN_KEY`, ODER
3. `cert_file` + `key_file` in der Config

**Egress-Log-Beweis (Test "test batata"):**
```
12:13:13 - Failed to send packet: CreatePermission error response (error 403:)
12:13:14 - ICE connected (nach Fehlern)
12:13:30 - egress_complete
```

**Ursachenkette:** TURN `enabled: true` ohne TLS-Cert → eingebauter TURN-Server kann keine TURN-TLS-Verbindung aufbauen → **403 CreatePermission** → Audio-Pakete gehen verloren → Recording nur 3964 Bytes (fast leer) → leere Transkription → leeres PV. Das erklaert auch, warum "test 67" (154KB, direkter UDP-Pfad) funktionierte und "test batata" (TURN-Pfad) leer war — **gleicher Zustand vor und nach Helm**.

#### 3. Loesung

- **Empfohlen:** `turn.enabled: false` (direkter UDP-Pfad reicht im Cluster; Beweis: "test 67" erfolgreich mit 154KB).
- **Alternativ (nur wenn TURN zwingend):** TURN mit TLS-Zertifikat konfigurieren (`secretName` + `domain`).
- `force_tcp`, `allow_tcp_fallback`, `tcp_fallback_rtt_threshold` sind KEINE gueltigen LiveKit-Chart-Keys — entfernt.

**Referenz:** `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` (vollstaendiger Prompt fuer den Wiederaufbau).

### Verifizierung
- ✅ Pod Running: `livekit-config-staging-764ff6b6bb-lddqp` (Node: instance-20260329-0846)
- ✅ Service: `livekit-config-staging` ClusterIP 10.43.99.173 (Port 7880)
- ✅ Endpoints: 10.0.0.191:7880, 10.0.0.191:7881
- ✅ Labels: `app.kubernetes.io/name: livekit-config-staging`
- ✅ Egress -> LiveKit: OK (wget successful)
- ✅ Server Logs: Redis verbunden, TURN gestartet
- ✅ hostNetwork: true (IP 10.0.0.191 = Node IP)

### Recording Test (2026-08-06)
- ✅ Login als dg@meeting.tn
- ✅ Meeting erstellt (adc7b664-1d91-44da-9f51-8e8a26867532)
- ✅ Recording gestartet (EG_F7wmWaWpazF3)
- ✅ Audio gesendet (test_audio.ogg)
- ✅ Recording gestoppt
- ✅ Webhook (egress_ended) empfangen
- ✅ Recording Status: completed (file_size: 154753 bytes)
- ✅ Transkription: completed
- ✅ PV erstellt (ID: 1f385e67-ba61-452d-b916-192d50f32ebc)
- ✅ PV Status: draft
- ✅ PV Content: Verschluesselt (Fernet, 164 Zeichen)

### Pipeline Status
- **Recording**: Funktioniert
- **Transkription**: Funktioniert
- **PV**: Funktioniert (draft Status)
- **Egress**: Funktioniert (hostNetwork: true)

### Naechste Schritte
1. Egress migrieren (Helm Chart) - Optional
2. Production Migration planen
3. Monitoring einrichten
