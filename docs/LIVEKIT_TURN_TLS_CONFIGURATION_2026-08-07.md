# LiveKit TURN TLS — Offizielle Doku + Implementierungs-Plan (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **Kontext**: TURN UDP (3478) funktioniert, aber TLS (5349) braucht ein Zertifikat
- **Crash-Grund**: `turn.tls_port: 5349` OHNE `cert_file`/`key_file` → `TURN tls cert required`
- **Status**: ⏳ DOKUMENTIERT, WARTET AUF FREIGABE

---

## 1. Der Crash (100% belegt)

### 1.1 Fehlermeldung (aus LiveKit Server Logs)
```
TURN tls cert required: open : no such file or directory
```

### 1.2 Ursache
```yaml
# VORHER (verursacht Crash):
turn:
  enabled: true
  udp_port: 3478
  tls_port: 5349    # ← Port gesetzt, aber KEIN Zertifikat!
```

### 1.3 Lösung (nach LiveKit-Doku)
```yaml
# NACHHER (ohne tls_port — nur UDP-TURN):
turn:
  enabled: true
  udp_port: 3478
  # tls_port: 5349  # ← ENTFERNT (kein Zertifikat vorhanden)
```

---

## 2. Offizielle LiveKit-TURN-TLS-Doku (100% Quellen)

### 2.1 Exakte Config-Keys (aus config-sample.yaml)

**Quelle: github.com/livekit/livekit (config-sample.yaml)**
```yaml
turn:
  # Enables the embedded TURN server (defaults to false)
  enabled: true
  
  # TURN/UDP port (defaults to 3478)
  udp_port: 3478
  
  # TURN/TLS port (defaults to 5349)
  # MUST be 443 if not running behind a load balancer
  tls_port: 5349
  
  # Domain name that must match the TLS certificate
  domain: turn.myhost.com
  
  # Set to true if using an L4 load balancer to terminate TLS
  external_tls: false
  
  # Paths to TLS certificate and private key (PEM format)
  cert_file: /path/to/turn.crt
  key_file: /path/to/turn.key
  
  # TTL of TURN credentials in seconds (defaults to 300)
  ttl_seconds: 300
```

### 2.2 Kubernetes-Deployment (aus Helm Chart)

**Quelle: github.com/livekit/livekit-helm (server-sample.yaml)**
```yaml
turn:
  enabled: true
  domain: turn.myhost.com
  tls_port: 5349
  udp_port: 3478
  # Kubernetes Secret containing TLS cert
  secretName: <tlssecret>
```

### 2.3 Certificate-Format

| Eigenschaft | Wert |
|---|---|
| **Format** | PEM (Standard für Go/TLS) |
| **Dateien** | `cert.pem` (Zertifikat) + `key.pem` (privater Schlüssel) |
| ** CN** | Muss mit `turn.domain` übereinstimmen |

### 2.4 Self-Signed vs. Trusted CA

**Quelle: docs.livekit.io (Self-Hosting Deployment)**
> „The SSL certificate must be signed by a trusted certificate authority; self-signed certs do not work here."

**Begründung:**
- WebRTC-Clients (Browser) enforce strict TLS-Policies
- Self-Signed → Client rejected TLS-Handshake
- **Für Staging/Production: Let's Encrypt (kostenlos)**

### 2.5 tls_port: 443 vs. 5349

**Quelle: docs.livekit.io (Ports & Firewall)**
> „If running without a load balancer, tls_port must be set to 443 because corporate firewalls heavily restrict outbound connections."

| Deployment | Empfohlener tls_port |
|---|---|
| Ohne Load Balancer | **443** (Firewall-friendly) |
| Mit L4 Load Balancer | 5349 (Standard) |
| Hinter Cloudflare | 443 (Cloudflare terminiert TLS) |

---

## 3. Implementierungs-Plan (nach offizieller Doku)

### Option A: TURN TLS mit Let's Encrypt (empfohlen für Production)

#### Schritt 1: cert-manager Certificate erstellen
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: livekit-turn-tls
  namespace: meeting-automation-staging
spec:
  secretName: livekit-turn-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - turn.staging.meeting-automation.com
```

#### Schritt 2: DNS-Eintrag erstellen
```
turn.staging.meeting-automation.com → Public IP (158.180.18.110)
```

#### Schritt 3: ConfigMap mit tls_port + cert_file
```yaml
turn:
  enabled: true
  domain: turn.staging.meeting-automation.com
  udp_port: 3478
  tls_port: 443          # Firewall-friendly
  cert_file: /etc/livekit/tls/tls.crt
  key_file: /etc/livekit/tls/tls.key
```

#### Schritt 4: Deployment — Secret mounten
```yaml
volumes:
  - name: turn-tls
    secret:
      secretName: livekit-turn-tls-secret
containers:
  - volumeMounts:
      - name: turn-tls
        mountPath: /etc/livekit/tls
        readOnly: true
```

#### Schritt 5: Firewall öffnen
```bash
# Port 443/tcp (TURN TLS)
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

#### Schritt 6: OCI Security List
```
Ingress Rule: TCP 443 (0.0.0.0/0) — TURN TLS
```

---

### Option B: TURN nur UDP (aktuell, ohne TLS)

**Status: AKTIV (nach Crash-Fix)**

```yaml
turn:
  enabled: true
  udp_port: 3478
  # tls_port: NICHT GESETZT (kein TLS)
```

| Port | Status |
|---|---|
| 3478/UDP | ✅ OPEN (firewalld) |
| 5349/TCP | ❌ Nicht benötigt (kein TLS) |

---

## 4. Vergleich: UDP vs. TLS TURN

| Eigenschaft | UDP TURN (3478) | TLS TURN (5349/443) |
|---|---|---|
| **Verschlüsselung** | ❌ Keine | ✅ TLS |
| **Firewall** | ✅ Meistens offen | ⚠️ 443 meistens offen |
| **Performance** | ✅ Schneller | ⚠️ TLS-Overhead |
| **Sicherheit** | ⚠️ Nur SRTP | ✅ SRTP + TLS |
| **Enterprise** | ❌ Oft blockiert | ✅ Meistens erlaubt |
| **Empfehlung** | Staging/Testing | Production |

---

## 5. Aktueller Status (nach Crash-Fix)

### Was jetzt läuft
```yaml
turn:
  enabled: true
  udp_port: 3478
  # KEIN tls_port (Crash verhindert)
```

### Was getestet werden muss
1. **TURN UDP funktioniert?** — Client sollte TURN-Relay als ICE-Kandidat erhalten
2. **Verbindung stabil?** — Kein CLIENT_REQUEST_LEAVE nach 15s
3. **Recording funktioniert?** — Audio wird über TURN-Relay gesendet

### Nächster Schritt (nach User-Freigabe)
1. User testet mit aktueller Config (TURN UDP)
2. Bei Erfolg: Option B (UDP) beibehalten
3. Für Production: Option A (TLS) implementieren

---

## 6. Referenzen (100% offizielle Quellen)

| Quelle | Link | Inhalt |
|---|---|---|
| LiveKit Config Sample | github.com/livekit/livekit (config-sample.yaml) | TURN YAML-Keys |
| LiveKit Helm Chart | github.com/livekit/livekit-helm | turn.secretName |
| LiveKit Self-Hosting | docs.livekit.io/transport/self-hosting | TLS-Anforderung |
| LiveKit Ports | docs.livekit.io/transport/self-hosting/ports-firewall | tls_port: 443 |

---

## 7. Zusammenfassung

| Fakt | Wert |
|---|---|
| **Crash-Grund** | `tls_port: 5349` ohne `cert_file`/`key_file` |
| **Fix** | `tls_port` entfernt → nur UDP-TURN (3478) |
| **Self-Signed** | ❌ Nicht unterstützt (WebRTC-Policy) |
| **Empfehlung** | UDP für Staging, TLS mit Let's Encrypt für Production |
| **Nächster Schritt** | User testet TURN UDP → bei Erfolg: Production-Plan |
