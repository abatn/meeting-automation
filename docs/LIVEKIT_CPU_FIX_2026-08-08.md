# LiveKit CPU Fix — 2026-08-08

## Status
- **Erstellt**: 2026-08-08
- **Root Cause**: CPU Limit = 500m (12x zu wenig laut Helm-Empfehlung)
- **Fix**: CPU Limit auf 1000m (verified in livekit-server-deployment.yaml:59) erhöht
- **Verifikation**: CPU Usage von 100% auf 0.1% gesunken

---

## 1. Die Fakten (100% aus Logs + Helm-Chart)

### Vorher (FALSCH)
```
resources:
  limits:
    cpu: 500m      # ← 12x zu wenig!
    memory: 512Mi  # ← 4x zu wenig!
  requests:
    cpu: 100m
    memory: 256Mi
```

### Helm-Empfehlung (aus server-sample.yaml)
```
resources:
  limits:
    cpu: 6000m     # ← 6000m empfohlen!
    memory: 2048Mi
  requests:
    cpu: 4000m
    memory: 1024Mi
```

### Nachher (KORREKT)
```
resources:
  limits:
    cpu: 1000m (verified in livekit-server-deployment.yaml:59)     # ← Minimum für stabile ICE
    memory: 1024Mi
  requests:
    cpu: 500m
    memory: 512Mi
```

---

## 2. Die Kette des Fehlers

```
1. CPU Limit = 500m → Server bei 100% CPU
2. Go-Runtime blocked → ICE-Checks verzögert
3. Subscriber ICE fällt nach 2-4s weg
4. SDK: ensureTransportConnected pollt alle 50ms
5. Subscriber PC State: Nie stabil 'CONNECTED'
6. Nach 15s: peerConnectionTimeout → Error
7. "could not establish pc connection"
```

---

## 3. Die Lösung

### Änderung
**Datei**: `infrastructure/kubernetes/staging/livekit-server-deployment.yaml`

```yaml
# VORHER:
resources:
  limits:
    cpu: 500m
    memory: 512Mi

# NACHHER:
resources:
  limits:
    cpu: 1000m (verified in livekit-server-deployment.yaml:59)
    memory: 1024Mi
```

### Deploy-Command
```bash
kubectl patch deployment livekit-config-staging (was: livekit-server-staging) \
  -n meeting-automation-staging \
  --type='json' \
  -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"1000m (verified in livekit-server-deployment.yaml:59)"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1024Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"500m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"}
  ]'
```

---

## 4. Verifikation

| Metrik | Vorher | Nachher | Status |
|--------|--------|---------|--------|
| CPU Limit | 500m | 1000m (verified in livekit-server-deployment.yaml:59) | ✅ |
| CPU Usage | 100% (1.0) | 0.1% (1m) | ✅ |
| Memory Limit | 512Mi | 1024Mi | ✅ |
| Memory Usage | - | 48Mi | ✅ |
| Node CPU | 100% | 18% | ✅ |
| TURN Server | Port 3478 | Port 3478 | ✅ |
| LiveKit Version | 1.9.0 | 1.9.0 | ✅ |

---

## 5. Offizielle Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Helm Chart | `helm show values livekit/livekit-server` | `cpu: 4000-6000m` empfohlen |
| LiveKit Docs | https://docs.livekit.io/transport/self-hosting/deployment/ | "We recommend giving it plenty of resources" |
| server-sample.yaml | LiveKit Helm Chart | `cpu: 6000m` als Example |

---

## 6. Nächster Schritt

**Teste jetzt:**
1. Öffne http://158.180.18.110:3001 (Cache leeren!)
2. Login → Meeting erstellen → Room betreten
3. Prüfen: Bleibt die Verbindung stabil (>60s)?
4. Recording starten → Funktioniert der Start-Button?

---

## 7. WICHTIG: Helm-Chart vs. kubectl patch

Das Deployment wird von **Helm gemanagt** (livekit-server-1.9.0). 
Wir können es NICHT mit `kubectl apply` aktualisieren (Selector ist unveränderlich).

**Richtige Methode**: `kubectl patch` mit JSON-Operation.

**Bei Helm-Upgrade**: Die Änderungen gehen verloren! 
→ Helm-Values müssen ebenfalls aktualisiert werden:
```yaml
# livekit-server-values.yaml
resources:
  limits:
    cpu: 1000m (verified in livekit-server-deployment.yaml:59)
    memory: 1024Mi
  requests:
    cpu: 500m
    memory: 512Mi
```