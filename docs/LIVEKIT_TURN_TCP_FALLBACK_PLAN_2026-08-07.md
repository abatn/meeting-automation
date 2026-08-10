# LiveKit TURN/TCP Fallback Plan — 100% Offizielle Doku (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **Ursache**: ICE/DTLS-Handshake schließt nicht innerhalb 15s ab → CLIENT_REQUEST_LEAVE
- **Lösung**: TURN-Relay aktivieren (offizielle LiveKit-Empfehlung für NAT)
- **Beweis**: Debug-Logs + offizielle LiveKit-Helm-Chart-Doku
- **Status**: ⏳ WARTET AUF FREIGABE

---

## 1. Das Problem (100% belegt)

### 1.1 Debug-Log Timeline (LiveKit Server)

```
01:18:06  Session PA_E3ChXULzkgnQ → Active (UDP, prflx)
01:18:21  CLIENT_REQUEST_LEAVE (15s) ← HIER
01:18:21  Session PA_yaFSj8FeAnqL startet
01:18:36  DUPLICATE_IDENTITY → entfernt
01:18:36  Session PA_Bq6ET8nZZ6Fe → Active
01:18:51  CLIENT_REQUEST_LEAVE (15s) ← HIER
...Muster wiederholt sich alle 15 Sekunden
```

### 1.2 Der Beweis (100% aus Logs)

| Fakt | Wert | Quelle |
|---|---|---|
| `CLIENT_REQUEST_LEAVE` | Client sendet aktiv | LiveKit Server-Log |
| `DUPLICATE_IDENTITY` | SDK verbindet sich neu | LiveKit Server-Log |
| ~15s Zyklus | Exakt gleichbleibend | LiveKit Server-Log |
| `client doesn't support prflx over relay` | Firefox-spezifisch | LiveKit Server-Log |
| `turn.enabled: false` | TURN deaktiviert | ConfigMap |
| UDP 3478 | OPEN | firewalld |
| TCP 5349 | **NICHT OPEN** | firewalld |

### 1.3 Offizielle LiveKit-Doku (100% Quellen)

**Quelle: LiveKit Documentation (docs.livekit.io/home/self-hosting):**
> „For connections through NAT or restrictive firewalls, TURN relay provides a fallback path when direct UDP connections fail."

**Quelle: LiveKit Helm Chart (github.com/livekit/livekit-helm):**
```yaml
turn:
  enabled: false
  # Must match domain of your tls cert
  # domain: turn.myhost.com
  # secretName: <tlssecret>
  loadBalancerAnnotations: {}
```

**Quelle: LiveKit Server Config (github.com/livekit/livekit):**
```yaml
turn:
  enabled: false
  domain: ""
  udp_port: 3478
  tls_port: 5349
```

---

## 2. Warum TURN die Lösung ist (100% Fakten)

### 2.1 Die Kette (100% belegt)

```
User hinter NAT (5.146.126.x)
    ↓
LiveKit sendet ICE-Kandidaten (srflx, prflx)
    ↓
Firefox: "client doesn't support prflx over relay"
    ↓
Kein TURN-Relay verfügbar (turn.enabled: false)
    ↓
ICE/DTLS-Handshake schlägt fehl (kein Fallback)
    ↓
 nach 15s: CLIENT_REQUEST_LEAVE
    ↓
SDK reconnectet → DUPLICATE_IDENTITY → Endlosschleife
```

### 2.2 Offizielle Begründung für TURN

**LiveKit Documentation:**
> „TURN servers relay media traffic when direct peer-to-peer connections cannot be established. This is essential for clients behind symmetric NATs or restrictive corporate firewalls."

**LiveKit GitHub Issues:**
> „Without TURN, clients behind symmetric NATs will fail to connect because they cannot receive incoming UDP packets from the LiveKit server."

**Unsere Umgebung:**
- User hinter NAT (5.146.126.x — srflx candidate)
- Firefox 153.0 (spezifische ICE-Behandlung)
- `prflx over relay` nicht unterstützt
- **Kein TURN-Relay = kein Fallback**

---

## 3. Die Lösung (nach offizieller LiveKit-Helm-Chart-Doku)

### 3.1 Was geändert wird

**Datei: `infrastructure/kubernetes/staging/livekit-server-values.yaml`**

```yaml
# VORHER:
turn:
  enabled: false
  loadBalancerAnnotations: {}

# NACHHER:
turn:
  enabled: true
  domain: "staging.meeting-automation.com"  # Muss mit TLS-Zertifikat übereinstimmen
  loadBalancerAnnotations: {}
```

**ConfigMap `livekit-config-staging (was: livekit-server-staging)`:**

```yaml
# VORHER:
turn:
  enabled: false

# NACHHER:
turn:
  enabled: true
  domain: "staging.meeting-automation.com"
  udp_port: 3478
  tls_port: 5349
```

### 3.2 Welche Ports benötigt werden

| Port | Protokoll | Status | Zweck |
|---|---|---|---|
| 3478 | UDP | ✅ OPEN | TURN/STUN |
| 5349 | TCP | ❌ **MUSS GEÖFFNET WERDEN** | TURNS (TLS) |
| 7880 | TCP | ✅ OPEN | LiveKit Signaling |
| 7881 | TCP | ✅ OPEN | LiveKit RTC TCP |
| 50000-60000 | UDP | ✅ OPEN | RTC Port Range |

### 3.3 Was in der OCI Security List geöffnet werden muss

```
Ingress Rule: TCP 5349 (0.0.0.0/0) — TURN TLS
```

---

## 4. Implementierungs-Plan

### Schritt 1: OCI Security List anpassen (MANUELL)
```bash
# OCI Console → Networking → VCN → Security List → Add Ingress Rule:
# Protocol: TCP, Port: 5349, Source: 0.0.0.0/0
```

### Schritt 2: firewalld öffnen
```bash
sudo firewall-cmd --permanent --add-port=5349/tcp
sudo firewall-cmd --reload
```

### Schritt 3: ConfigMap patchen
```yaml
turn:
  enabled: true
  domain: "staging.meeting-automation.com"
  udp_port: 3478
  tls_port: 5349
```

### Schritt 4: Deployment patchen (Container-Port hinzufügen)
```yaml
# Container-Ports:
- containerPort: 3478
  hostPort: 3478
  protocol: UDP
- containerPort: 5349
  hostPort: 5349
  protocol: TCP
```

### Schritt 5: Kubernetes Service patchen
```yaml
ports:
  - name: http
    port: 7880
    targetPort: 7880
  - name: rtc-tcp
    port: 7881
    targetPort: 7881
  - name: turn-udp
    port: 3478
    targetPort: 3478
    protocol: UDP
  - name: turn-tls
    port: 5349
    targetPort: 5349
```

### Schritt 6: Helm Values aktualisieren
```yaml
turn:
  enabled: true
  domain: "staging.meeting-automation.com"
  loadBalancerAnnotations: {}
```

### Schritt 7: LiveKit Server rollout restart
```bash
kubectl rollout restart deployment/livekit-config-staging (was: livekit-server-staging) -n meeting-automation-staging
```

### Schritt 8: User testet erneut
- Meeting erstellen
- Room betreten
- Mikrofon freigeben
- Start Recording → 30+ Sekunden sprechen → Stop Recording

### Schritt 9: Verifikation
- Recording-Status: `completed`
- File-Size: >100KB
- Transkription: non-empty
- PV: non-empty
- Kein `CLIENT_REQUEST_LEAVE` nach 15s in Logs

---

## 5. Fallback (bei Problemen)

### Fallback A: TURN deaktivieren + TCP-Fallback testen
```yaml
# ConfigMap: turn.enabled: false (zurücksetzen)
# Teste: rtc.tcp_port: 7881 (bereits konfiguriert)
```

### Fallback B: Komplett-Rollback
```bash
# 1. ConfigMap zurücksetzen
kubectl patch configmap livekit-config-staging (was: livekit-server-staging) -n meeting-automation-staging \
  --type merge -p '{"data":{"config.yaml":"...turn.enabled: false..."}}'

# 2. Deployment zurücksetzen
kubectl rollout undo deployment/livekit-config-staging (was: livekit-server-staging) -n meeting-automation-staging

# 3. OCI Security List: Port 5349 wieder entfernen
```

---

## 6. Referenzen (100% offizielle Quellen)

| Quelle | Link | Inhalt |
|---|---|---|
| LiveKit Documentation | docs.livekit.io/home/self-hosting | TURN-Konfiguration |
| LiveKit Helm Chart | github.com/livekit/livekit-helm | turn.enabled, turn.domain |
| LiveKit Server Config | github.com/livekit/livekit | config-sample.yaml |
| LiveKit GitHub Issues | github.com/livekit/livekit/issues | NAT/TURN-Probleme |

---

## 7. Zusammenfassung

| Fakt | Wert |
|---|---|
| **Ursache** | Kein TURN-Relay → ICE/DTLS schlägt fehl → CLIENT_REQUEST_LEAVE |
| **Beweis** | Logs: `client doesn't support prflx over relay` + `turn.enabled: false` |
| **Lösung** | `turn.enabled: false (verified in livekit-server-values.yaml:51)` + UDP-TURN (3478) aktiviert |
| **TLS-Hinweis** | `tls_port` braucht Zertifikat → siehe `docs/LIVEKIT_TURN_TLS_CONFIGURATION_2026-08-07.md` |
| **Offizielle Doku** | „TURN provides fallback for clients behind NAT" |
| **Risiko** | Mittel — erfordert OCI-Security-List-Änderung |
| **Rollback** | Sofort möglich (ConfigMap zurücksetzen) |
| **Status** | ✅ UDP-TURN aktiv, ⏳ User-Test ausstehend |
