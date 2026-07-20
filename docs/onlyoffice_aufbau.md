# OnlyOffice Aufbau — K3s Staging (2026-07-20)

## Status: ✅ FUNKTIONIERT

## Image
- `onlyoffice/documentserver:9.4.0` (Build 129)
- `imagePullPolicy: IfNotPresent`

## Architektur

```
Browser (HTTPS) → nginx-ingress (443) → onlyoffice-staging:80 (HTTP)
                                              ↓
                                         nginx → docservice (Node.js, Port 8000)
                                              ↓
                                         /cache/files/ (Editor.bin)
```

## Environment Variables (Deployment)

| Variable | Wert | Zweck |
|----------|------|-------|
| `JWT_ENABLED` | `true` | JWT-Validierung aktiviert |
| `JWT_SECRET` | `staging-onlyoffice-secret-jwt-key-2026` | JWT-Schlüssel |
| `JWT_HEADER` | `Authorization` | HTTP-Header für JWT |
| `ALLOW_PRIVATE_IP_ADDRESS` | `true` | Erlaubt interne K8s-Adressen |
| `SERVER_NAME` | `staging.meeting-automation.com` | Externer Hostname |
| `SECURE_LINK_SECRET` | `gy3MA8R33ojtIGfXYq37` | muss mit `storage.fs.secretString` übereinstimmen |

## ConfigMap `onlyoffice-custom-config` (namespace: meeting-automation-staging)

Enthält 2 Dateien:

### 1. `local.json`
```json
{
  "services": {
    "CoAuthoring": {
      "token": {
        "enable": {
          "request": { "inbox": true, "outbox": true },
          "browser": true
        },
        "inbox": { "header": "Authorization", "inBody": false },
        "outbox": { "header": "Authorization", "inBody": false }
      },
      "secret": {
        "browser": { "string": "staging-onlyoffice-secret-jwt-key-2026" },
        "inbox": { "string": "staging-onlyoffice-secret-jwt-key-2026" },
        "outbox": { "string": "staging-onlyoffice-secret-jwt-key-2026" },
        "session": { "string": "staging-onlyoffice-secret-jwt-key-2026" }
      },
      "request-filtering-agent": {
        "allowPrivateIPAddress": true,
        "allowMetaIPAddress": true
      }
    }
  },
  "storage": {
    "fs": {
      "secretString": "gy3MA8R33ojtIGfXYq37"
    },
    "externalHost": "https://staging.meeting-automation.com"
  }
}
```

**Wichtige Werte:**
- `storage.externalHost`: Offizieller OnlyOffice-Parameter (api.onlyoffice.com) — sagt dem DocService die externe URL → generiert HTTPS-URLs für `/cache/files/`
- `storage.fs.secretString`: Muss identisch mit `SECURE_LINK_SECRET` Env-Var und nginx `$secure_link_secret` sein
- `allowMetaIPAddress`: Erlaubt Meta-IPs (Docker-Subnetze)

### 2. `ds-docservice.conf`
- Enthält `$the_scheme` (dynamisch, basierend auf `X-Forwarded-Proto` Header)
- Enthält `/cache/files/` Location mit `secure_link`-Validierung
- **NICHT hardcoded** — nutzt ConfigMap `onlyoffice-proxy-headers` für HTTPS

## ConfigMap `onlyoffice-proxy-headers` (namespace: ingress-nginx)

```yaml
data:
  X-Forwarded-Host: "staging.meeting-automation.com"
  X-Forwarded-Proto: "https"
```

Wird vom Ingress via `nginx.ingress.kubernetes.io/proxy-set-headers` Referenz.

## Deployment Mounts

| Volume | Quelle | mountPath | subPath |
|--------|--------|-----------|---------|
| `configmap-source` | ConfigMap `onlyoffice-custom-config` | `/config-source` | — (read-only) |
| `onlyoffice-config-writable` | emptyDir | — | — |
| Main Container | `onlyoffice-config-writable` | `/etc/onlyoffice/documentserver/local.json` | `local.json` |
| Main Container | `onlyoffice-config-writable` | `/etc/onlyoffice/documentserver/nginx/includes/ds-docservice.conf` | `ds-docservice.conf` |

**Warum emptyDir + initContainer:**
Der OnlyOffice-Entry-Point (`run-document-server.sh`) schreibt JWT aus Env-Vars in `local.json`. ConfigMap via `subPath` ist read-only → Write scheitert (EBUSY). emptyDir ist beschreibbar.

```yaml
initContainers:
- name: init-oo-config
  image: onlyoffice/documentserver:9.4.0
  command: ['sh', '-c', 'cp /config-source/local.json /emptydir-writable/local.json && cp /config-source/ds-docservice.conf /emptydir-writable/ds-docservice.conf && chmod 644 /emptydir-writable/local.json /emptydir-writable/ds-docservice.conf']
```

## Ingress

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-set-headers: "ingress-nginx/onlyoffice-proxy-headers"
  nginx.ingress.kubernetes.io/websocket-services: "backend, livekit-server-staging, onlyoffice-staging"
paths:
  - /web-apps → onlyoffice-staging:80
  - /cache → onlyoffice-staging:80
  - /healthcheck → onlyoffice-staging:80
  - /doc → onlyoffice-staging:80
```

## NetworkPolicy (`onlyoffice-policy`)

Erlaubt OnlyOffice-Pod:
- DNS (53/UDP+TCP) Egress
- Backend (8000/TCP) Egress

## OnlyOffice → Backend Flow

```
Browser → config endpoint → Backend generiert DOCX + upload S3
       → Backend gibt Config zurück (document.url = interne URL)
       → OnlyOffice-Server fetcht document.url intern (HTTP 200)
       → OnlyOffice sendet Editor.bin via WebSocket an Browser
       → Browser rendert Editor
```

## HARTE LESSONS (diese Session)

| # | Regel |
|---|-------|
| O8 | **`storage.externalHost` ist der offizielle OnlyOffice-Parameter** für externe URL-Konfiguration (api.onlyoffice.com/docs). Leer = HTTP, gesetzt = HTTPS. |
| O9 | **`storage.fs.secretString` muss identisch mit `SECURE_LINK_SECRET` sein** — sonst 403 auf `/cache/files/`. nginx validiert MD5 gegen `$secure_link_secret`. |
| O10 | **`SECURE_LINK_SECRET` Env-Var verhindert zufällige Generierung** — Entry-Point nutzt `${SECURE_LINK_SECRET:-$(pwgen -s 20)}`. Ohne Env-Var generiert er bei jedem Start einen neuen Wert. |
| O11 | **ConfigMap via `subPath` ist read-only** — OnlyOffice-Entry-Point schreibt JWT in `local.json`. emptyDir + initContainer ist der korrekte Ansatz. |
| O12 | **`kubectl exec` Output muss bereinigt werden** — `Defaulted container...` wird in Dateien geschrieben → JSON parse error. |
| O13 | **Hardcoding ist verboten (Regel N8)** — `SECURE_LINK_SECRET` als Deployment-Env-Var ist erlaubt (deployment-spezifische Config). |

## Deploy-Checkliste

```bash
# 1. ConfigMap neu erstellen
kubectl create configmap onlyoffice-custom-config \
  --from-file=local.json=/pfad/zu/local.json \
  --from-file=ds-docservice.conf=/pfad/zu/ds-docservice.conf \
  -n meeting-automation-staging --dry-run=client -o yaml | kubectl apply -f -

# 2. Deployment anwenden
kubectl apply -f infrastructure/kubernetes/staging/onlyoffice-deployment.yaml

# 3. Pod neustarten
kubectl rollout restart deployment/onlyoffice-staging -n meeting-automation-staging

# 4. Verifizieren
kubectl exec -n meeting-automation-staging $(kubectl get pods -n meeting-automation-staging -l app=onlyoffice-staging -o name | head -1) -- python3 -c "
import json
with open('/etc/onlyoffice/documentserver/local.json') as f:
    d = json.load(f)
print('externalHost:', d['storage']['externalHost'])
print('secretString:', d['storage']['fs']['secretString'])
"

# 5. Editor testen
curl -sk -o /dev/null -w 'HTTP %{http_code}' 'https://staging.meeting-automation.com/editor/{pv_id}?lang=ar'
```
