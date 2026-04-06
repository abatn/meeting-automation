# OnlyOffice Nginx Redirect Problem & Solution

**Datum:** 2026-04-06  
**Betroffene Version:** OnlyOffice Document Server 7.1.1, 9.0.4 (ARM64)  
**Umgebung:** Docker Compose, externe VM (158.180.18.110)

---

## 🎯 Problem

**Symptom:** Beim Klick auf "Edit Online" öffnet sich der OnlyOffice Editor, aber die Seite bleibt **leer/weiß**. Keine Fehlermeldung im Browser.

**Beobachtungen:**

- Backend liefert OnlyOffice Config korrekt mit `onlyOfficeUrl: "http://158.180.18.110:8081"`
- Frontend lädt OnlyOffice JS von der richtigen URL
- OnlyOffice Container läuft und Port 8081 ist offen
- **Nginx redirectet auf `http://localhost/...`** statt auf die öffentliche IP

```
GET http://158.180.18.110:8081/web-apps/apps/documenteditor/
→ HTTP/1.1 302 Moved Temporarily
Location: http://localhost/9.0.4-76390656162cbc6053022373c417acc4/web-apps/apps/documenteditor/
```

Der Browser folgt dem Redirect zu `http://localhost/...` → kann `localhost` nicht auflösen (meint sich selbst, nicht den OnlyOffice Container) → leere Seite.

---

## 🔍 Root Cause

OnlyOffice Document Server verwendet **NGINX** als reverse proxy. NGINX generiert Redirect-URLs basierend auf:

1. Dem `Host`-Header aus der eingehenden Anfrage, **ODER**
2. Dem `server_name` aus der NGINX-Konfiguration, **ODER**
3. Dem System-Hostnamen des Containers (via `$hostname`)

Wenn in `docker-compose.yml` **kein `hostname:`** gesetzt ist, setzt Docker den Container-Namen (zufällige ID wie `ad5bac701297`) als Hostname. NGINX interpretiert das als `localhost` oder Container-internen Namen → Redirects gehen an die interne Adresse.

**In der Entwicklung** funktionierte es, weil:
- `ONLYOFFICE_URL="http://localhost:8080"` im Backend konfiguriert war
- Frontend lud Editor von `localhost` → Browser sah Redirect auf `localhost` als korrekt an (loopback)

**In der Produktion** (public IP) versagt:
- `ONLYOFFICE_URL="http://158.180.18.110:8081"`
- Browser lädt Editor von public IP
- OnlyOffice redirectet auf `localhost` → Browser versucht `localhost` (127.0.0.1) zu erreichen, nicht den OnlyOffice Server → **Connection refused** oder leere Seite

---

## ✅ Lösung

### Methode 1: Hostname setzen (empfohlen)

Füge zum `onlyoffice` Service in `docker-compose.yml` hinzu:

```yaml
onlyoffice:
  image: onlyoffice/documentserver:9.0.4  # oder latest-arm64
  restart: unless-stopped
  hostname: "${HOST_IP:-localhost}"  # ← DIESE ZEILE HINZUFÜGEN
  environment:
    - JWT_ENABLED=true
    - JWT_SECRET=${ONLYOFFICE_SECRET:-super_secret_jwt_key_onlyoffice_2026}
    - JWT_HEADER=Authorization
    - ALLOW_PRIVATE_IP_ADDRESS=true
  ports:
    - "8081:80"
  volumes:
    - onlyoffice_data:/var/www/onlyoffice/Data
```

**Wichtig:** `HOST_IP` muss in `.env` definiert sein:
```bash
HOST_IP=158.180.18.110
```

Dadurch erhalten alle Container den Hostnamen `158.180.18.110`. NGINX verwendet diesen für Redirects → Browser folgt Redirect zur public IP → funktioniert.

### Methode 2: Custom NGINX Config (alternativ)

Falls `hostname` nicht gesetzt werden kann/kann, erstelle `onlyoffice/nginx-config/custom.conf`:

```nginx
server {
    listen 80 default_server;
    server_name _;
    server_name_in_redirect off;
    port_in_redirect off;
}
```

Mount in `docker-compose.yml`:
```yaml
volumes:
  - onlyoffice_data:/var/www/onlyoffice/Data
  - ./onlyoffice/nginx-config/custom.conf:/etc/nginx/conf.d/custom.conf
```

`server_name_in_redirect off;` bewirkt, dass NGINX den `Host`-Header aus der Client-Anfrage für Redirects verwendet (statt `server_name`).

---

## 🧪 Test nach Fix

```bash
# 1. Container neu starten
docker compose up -d onlyoffice

# 2. Hostname prüfen
docker exec meeting-automation-onlyoffice-1 hostname
# → sollte 158.180.18.110 ausgeben (nichtContainer-ID)

# 3. Redirect testen
curl -I "http://158.180.18.110:8081/web-apps/apps/documenteditor/"
# Erwartet: HTTP/1.1 200 OK (kein 302 oder Location: http://localhost)

# 4. api.js prüfen
curl -I "http://158.180.18.110:8081/web-apps/apps/api/documents/api.js"
# Erwartet: HTTP/1.1 200 OK
```

---

## 📋 Verwandte Issues

- NurOffice Leere Seite (Edit Online)
- Nginx redirectet auf `localhost` oder Container-Hostname
- Browser kann keine Verbindung zu OnlyOffice herstellen

---

## 🔐 Security & ISO 27001 Hinweise

- Der Fix ändert **keine** Sicherheitseinstellungen (JWT, Token)
- Nur die Hostname-Konfiguration wird angepasst
- Keine Einführung von neuen Schwachstellen
- Kompatibel mit ISO 27001

---

## 📚 References

- OnlyOffice Docs: https://helpcenter.onlyoffice.com/installation/docs-community-install-docker.aspx
- Docker Compose `hostname`: https://docs.docker.com/compose/compose-file/compose-file-v3/#hostname
- Nginx `server_name_in_redirect`: http://nginx.org/en/docs/http/ngx_http_core_module.html#server_name_in_redirect
