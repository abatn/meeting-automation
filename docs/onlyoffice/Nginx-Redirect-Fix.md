# OnlyOffice Nginx Redirect Problem & Solution

**Datum:** 2026-04-06 (aktualisiert: 2026-06-21)  
**Betroffene Version:** OnlyOffice Document Server 7.1.1, 9.0.4, 9.3.1  
**Umgebung:** Docker Compose, externe VM (158.180.18.110)

---

## Problem

Beim Klick auf "Edit PV" öffnet sich der OnlyOffice Editor nicht — weiße Seite oder "An Error occurred while opening the file".

---

## Root Cause (Drei Bugs)

### Bug 1: `$host` stript Port — api.js lädt nie

`/api/` Block in nginx.conf verwendete `proxy_set_header Host $host;`.

- `$host` → `158.180.18.110` (Port weg!)
- `$http_host` → `158.180.18.110:3000` (mit Port)

Backend empfängt `Host: 158.180.18.110` → baut `onlyOfficeUrl = "http://158.180.18.110"` → Frontend lädt api.js von Port 80 → nichts da → **weiße Seite**.

### Bug 2: Regex匹配 fehlgeschlagen

Die ursprüngliche Regex:
```nginx
location ~ ^/[0-9]+\.[0-9]+\.[0-9]+[.\-]/ {
```

Erwartete: `/9.3.1-/` (Zeichenklasse `[.\-]` + `/`)
Tatsächlich: `/9.3.1-15f561f.../` (nach `-` kommt Hash, kein `/`)

→ Regex matched nie → `location /` fängt alles ab → SPA Index.html statt Proxy.

### Bug 3: `/cache/` Pfad nicht geproxied — "Error opening file"

NurOffice Editor lädt `Editor.bin` über `/cache/files/data/...`. Dieser Pfad wurde von `location /` als SPA Index ausgeliefert (397 Bytes) statt zu OnlyOffice geproxied.

---

## Lösung — nginx.conf

```nginx
# 1. $http_host in ALLEN Proxy-Blöcken (Port beibehalten)
proxy_set_header Host $http_host;

# 2. Regex angepasst (kein trailing / nach Zeichenklasse)
location ~ ^/[0-9]+\.[0-9]+\.[0-9]+[-.] { ... }

# 3. /cache/ Proxy für OnlyOffice Editor.bin
location /cache/ {
    proxy_pass http://onlyoffice:80;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
}
```

### Architektur

```
Browser → Port 3000 (nginx) → Port 80 (OnlyOffice intern)
         ├─ /web-apps/...           → proxy zu OnlyOffice (api.js, CSS, JS)
         ├─ /cache/...              → proxy zu OnlyOffice (Editor.bin)
         ├─ /9.3.1-.../web-apps/... → proxy zu OnlyOffice (versionierter Redirect)
         ├─ /healthcheck            → proxy zu OnlyOffice
         ├─ /api/...                → proxy zu Backend
         └─ alle anderen            → SPA (React)
```

---

## Alle Änderungen

| Datei | Was geändert |
|-------|-------------|
| `frontend/nginx.conf` | `$host` → `$http_host` in `/api/` und `/websockets/` |
| `frontend/nginx.conf` | `X-Forwarded-Host $http_host` in OnlyOffice Proxy-Blöcken |
| `frontend/nginx.conf` | Regex `[.\-]/` → `[-.]` |
| `frontend/nginx.conf` | Neue `location /cache/` für Editor.bin |
| `backend/app/api/v1/livekit.py` | LiveKit URL dynamisch aus Host-Header |
| `backend/app/api/v1/pv.py` | onlyOfficeUrl dynamisch aus Host-Header |

---

## Testen nach Fix

```bash
# 1. Frontend neu bauen
docker compose build --no-cache frontend
docker compose up -d frontend

# 2. api.js Proxy testen
curl -sI http://HOST:3000/web-apps/apps/api/documents/api.js
# → 200 OK, Content-Type: application/javascript

# 3. Redirect testen (Port muss in URL stehen)
curl -sI http://HOST:3000/web-apps/apps/documenteditor/
# → 302 mit Location: http://HOST:3000/9.3.1-.../web-apps/...

# 4. /cache/ Proxy testen
curl -sI http://HOST:3000/cache/files/data/test/Editor.bin/Editor.bin
# → 403 (von OnlyOffice, nicht SPA Index.html)

# 5. OnlyOffice Logs prüfen
docker logs meeting-automation-onlyoffice-1 | tail -5
# → host: "158.180.18.110" (nicht "onlyoffice")
```

---

## HTTPS in Produktion

**Voraussetzung:** Ein TLS-Terminator (nginx, Traefik, Cloud Load Balancer) vor unserem nginx.

### Was geändert werden muss

1. **`X-Forwarded-Proto` Header** — TLS-Terminator setzt `https`, muss weitergeleitet werden:
   ```nginx
   map $http_x_forwarded_proto $forwarded_proto {
       default $scheme;
       https   https;
   }
   proxy_set_header X-Forwarded-Proto $forwarded_proto;
   ```
   Ohne dieses Mapping → OnlyOffice Redirect-URLs nutzen `http://` → **Mixed Content**.

2. **Cookie Secure Flag** — JWT Cookies müssen `Secure` und `SameSite=None` haben bei HTTPS.

3. **WebSocket** — `wss://` statt `ws://` (wird vom Frontend automatisch erkannt bei HTTPS).

4. **CORS** — `CORS_ORIGINS` muss `https://domain.de` statt `http://IP:3000` enthalten.

### Vorgehen

```bash
# 1. TLS-Terminator konfigurieren (z.B. nginx auf Port 443)
# 2. nginx.conf anpassen (map-Block + $forwarded_proto)
# 3. Frontend neu bauen
# 4. OnlyOffice Editor mit HTTPS testen
```

### Bekannte Fallstricke

- OnlyOffice generiert Redirect-URLs basierend auf `X-Forwarded-Host` — muss Port 443 enthalten (nicht 3000)
- `X-Forwarded-Proto: https` muss an Backend UND OnlyOffice weitergeleitet werden
- LiveKit muss ebenfalls auf WSS umgestellt werden (`wss://domain.de` statt `ws://IP:7880`)

---

## Verwandte Issues

- OnlyOffice Leere Seite (api.js lädt nicht)
- "An Error occurred while opening the file" (/cache/ nicht geproxied)
- Nginx redirectet auf falschen Port
- Regex matching für versionierte Pfade

---

## Security & ISO 27001

- Der Fix ändert **keine** Sicherheitseinstellungen (JWT, Token)
- Nur Hostname- und Header-Konfiguration wird angepasst
- `X-Forwarded-Host` und `X-Forwarded-Proto` sind Standard-Header für Reverse Proxies
- Kompatibel mit ISO 27001

---

## References

- OnlyOffice Docs: https://helpcenter.onlyoffice.com/installation/docs-community-install-docker.aspx
- Nginx `$host` vs `$http_host`: http://nginx.org/en/docs/http/ngx_http_core_module.html#var_host
- Nginx `proxy_set_header`: http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header
