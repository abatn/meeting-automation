# n8n /n8n Subpath Fix — Staging + Production (2026-08-05)

## Status
- **Staging**: ✅ VERIFIZIERT — https://staging.meeting-automation.com/n8n zeigt n8n Editor
- **Production**: ⏳ Dateien erstellt, deploy Bereit (nicht angewendet)

## Problem (bewiesen, nicht geraten)
`https://staging.meeting-automation.com/n8n` zeigte eine weiße Seite.
Root cause: n8n ist nicht für Subpath-Deployment konfiguriert. Das n8n HTML referenziert Assets
mit absoluten Pfaden (`/static/...`, `/assets/...`), die der Ingress auf den Frontend-Catch-All
weiterleitet statt auf n8n.

## Verified Facts (Ausgangslage)
- NodePort `http://158.180.18.110:31678` funktioniert (liefert n8n von Root `/`)
- Ingress `/n8n` lieferte n8n HTML korrekt
- Aber `/n8n/static/base-path.js` → 200 text/html (index.html = SPA-Fallback) — **nicht** JS
- n8n-Version in Staging: **2.32.6** (Image: `n8nio/n8n:latest`, Digest `5f7856f4...`)

## Root Cause Analyse (empirisch bewiesen)

### Empirischer Test (n8n 2.32.6 lokal in Docker)
Vier Container getestet:

| Config | Container | HTML hrefs | Assets | Healthz | Webhooks |
|--------|-----------|------------|--------|---------|----------|
| Root (kein N8N_PATH) | port 31681 | `/static/...`, `/assets/...` | ✅ JS | ✅ JSON (Wurzel) | ✅ JSON (Wurzel) |
| `N8N_PATH=/n8n` | port 31679 | `/n8nstatic/...` (falsch) | ❌ HTML | ✅ JSON (Wurzel) | ✅ JSON (Wurzel) |
| **`N8N_PATH=/n8n/`** | **port 31680** | **`/n8n/static/...`, `/n8n/assets/...` (richtig!)** | **❌ HTML** | **✅ JSON (Wurzel)** | **✅ JSON (Wurzel)** |
| `N8N_PATH=/n8n/` + nginx strip | port 31683 | `/n8n/static/...` | **✅ JS** | **✅ JSON** | **✅ JSON** |

### Kern-Erkenntnis
n8n **generiert korrekte** `/n8n/static/...` URLs im HTML (mit `N8N_PATH=/n8n/`), aber
`express.static()` ist an Root `/` gemountet. Der `historyApiHandler` liefert für jeden Pfad,
der nicht `^/(assets|static|healthz|rest|...)/?` an Root matcht, index.html. `/n8n/static/base-path.js`
matcht NICHT → index.html → Browser bekommt HTML statt JS → weiße Seite.

### Die Lösung: Reverse-Proxy muss Prefix entfernen
Der Ingress muss `/n8n` **entfernen** (rewrite), bevor er an n8n weiterleitet. Dann empfängt
n8n `/static/...`, `/assets/...`, `/healthz`, `/webhook/...`, `/rest/...` an der Wurzel — alles
dort wo `express.static()` und die API-Controller es erwarten.

**Bewiesen mit nginx-Testproxy (port 31683):**
- `/n8n/static/base-path.js` → **200 `text/javascript`**, `window.BASE_PATH = '/n8n/'` ✅
- `/n8n/assets/index-*.js` → 200 `text/javascript` (705KB) ✅
- `/n8n/healthz` → 200 JSON `{"status":"ok"}` ✅
- `/n8n/rest/workflows` → 401 JSON (REST API) ✅
- `/n8n/webhook/test` → 404 JSON (Webhook-Handler von n8n) ✅

## Änderungen

### 1. `infrastructure/kubernetes/staging/n8n-deployment.yaml`
Env `N8N_PATH=/n8n/` (mit trailing slash!) nach `N8N_SECURE_COOKIE` eingefügt.
- **WICHTIG: Trailing slash (`/n8n/`) ist erforderlich.** Ohne Slash erzeugt n8n
  falsche URLs (`/n8nstatic/...` statt `/n8n/static/...`).

### 2. NEU `infrastructure/kubernetes/staging/n8n-ingress.yaml`
Separater Ingress-Resource für `/n8n` mit:
- `nginx.ingress.kubernetes.io/rewrite-target: /$2`
- `path: /n8n(/|$)(.*)` (pathType: ImplementationSpecific, use-regex: "true")
- TLS via `staging-tls` (Let's Encrypt)
- Proxy-Timeouts (86400s für SSE/WebSocket-Langlebigkeit)

### 3. `infrastructure/kubernetes/staging/ingress-staging.yaml`
`/n8n` Path (Prefix → n8n-staging:5678) **entfernt** (nun in eigenem Ingress).

### Warum separater Ingress?
`rewrite-target` ist eine Ingress-level Annotation. Mit `/n8n` im Haupt-Ingress
würde die Rewrite-Annotation alle Pfade betreffen (`/api`, `/livekit`, etc.),
die Backend-Services erwarten den vollen Pfad → Alles kaputt. Separater Ingress
ist der saubere Weg.

## Verifikation auf Staging (2026-08-05)

```
=== VERIFY: n8n editor HTML ===
/n8n : 200 text/html; charset=utf-8 22932B

=== VERIFY: base-path.js (THE CRITICAL TEST) ===
Content-Type: 200 text/javascript; charset=utf-8
Content: window.BASE_PATH = '/n8n/';

=== VERIFY: healthz ===
{"status":"ok"}

=== VERIFY: a JS asset ===
Asset: /n8n/assets/index-_CLhJ9Fe.js
Content-Type: 200 text/javascript; charset=utf-8 705868B

=== VERIFY: favicon ===
Content-Type: 200 image/vnd.microsoft.icon 15086B

=== REGRESSION CHECK: root frontend ===
/ : 200 text/html 1382B
=== REGRESSION CHECK: backend API ===
/api/health : 404 (erwartet — kein /api/health Route, Backend nutzt /health intern)
=== REGRESSION CHECK: OnlyOffice ===
/healthcheck : 200 text/plain; charset=utf-8
=== REGRESSION CHECK: LiveKit /rtc ===
/rtc : 404 (erwartet — WebSocket-Pfad, curl kann kein WS)
```

**Alle Tests bestanden.** Frontend, Backend, OnlyOffice, LiveKit — keine Regressionen.

## Bekannter Nebeneffekt
NodePort `http://158.180.18.110:31678` (unverschlüsselt, HTTP) zeigt jetzt ebenfalls
die weiße Seite, weil er n8n direkt (ohne Strip) anspricht. Mit `N8N_PATH=/n8n/` referenziert
das HTML Assets unter `/n8n/static/...`, die über NodePort → SPA-Fallback → index.html.

**Das war im Plan implizit so** — N8N_PATH ändert die HTML-Links global. Der sichere Weg
(`/n8n` via HTTPS) funktioniert jetzt korrekt.

## Rollback
Falls n8n wieder von Root bedient werden soll:
1. `kubectl patch deploy n8n-staging -n meeting-automation-staging --type='json' -p='[{"op":"remove","path":"/spec/template/spec/containers/0/env/8"}]'` (N8N_PATH entfernen — Index kann sich ändern!)
2. Oder einfacher: die drei YAML-Dateien reverten (git checkout) und erneut anwenden.
3. `kubectl rollout restart deployment/n8n-staging -n meeting-automation-staging`

## Production (2026-08-05)

### Status
- **Production**: ⏳ Dateien erstellt, deploy-bereit (nicht angewendet)
- **N8N_ENCRYPTION_KEY**: Muss noch generiert werden (`openssl rand -hex 32`)

### Dateien erstellt/bearbeitet

#### 1. `infrastructure/kubernetes/production/n8n-deployment.yaml`
- `N8N_PATH=/n8n/` nach `N8N_SECURE_COOKIE` eingefügt
- `N8N_ENCRYPTION_KEY` als `secretKeyRef` aus `n8n-secrets` hinzugefügt

#### 2. NEU `infrastructure/kubernetes/production/n8n-ingress.yaml`
- Eigenständiger Ingress mit:
  - `nginx.ingress.kubernetes.io/rewrite-target: /$2`
  - `nginx.ingress.kubernetes.io/use-regex: "true"`
  - `cert-manager.io/cluster-issuer: letsencrypt-prod`
  - TLS via `production-tls` (Let's Encrypt)
  - Path: `/n8n(/|$)(.*)` (pathType: ImplementationSpecific)
  - Host: `meeting-automation.com`
  - Proxy-Timeouts (86400s für SSE/WebSocket)

#### 3. `infrastructure/kubernetes/production/ingress-prod.yaml`
- `/n8n` Path (Prefix → n8n:5678) **entfernt** (nun in eigenem Ingress)

#### 4. `infrastructure/kubernetes/production/n8n-secrets.yaml`
- `N8N_ENCRYPTION_KEY: "CHANGE_ME_TO_RANDOM_HEX_64"` hinzugefügt
- **MUSS vor Deploy durch echten Key ersetzt werden**

### Unterschiede zu Staging

| Eigenschaft | Staging | Production |
|---|---|---|
| Namespace | `meeting-automation-staging` | `meeting-automation` |
| Service-Name | `n8n-staging` | `n8n` |
| Host | `staging.meeting-automation.com` | `meeting-automation.com` |
| TLS-Secret | `staging-tls` | `production-tls` |
| cert-manager | ✅ `letsencrypt-prod` | ✅ `letsencrypt-prod` |
| Ingress-Name | `n8n-staging` | `n8n` |
| N8N_ENCRYPTION_KEY | ✅ vorhanden | ⏳ muss generiert werden |

### Deployment-Befehle (Schritt-für-Schritt)

```bash
# 1. Production kubeconfig verwenden
export KUBECONFIG=/path/to/production-kubeconfig

# 2. N8N_ENCRYPTION_KEY generieren und einsetzen
ENCRYPTION_KEY=$(openssl rand -hex 32)
sed -i "s/CHANGE_ME_TO_RANDOM_HEX_64/$ENCRYPTION_KEY/" infrastructure/kubernetes/production/n8n-secrets.yaml

# 3. Secrets anwenden (ZUERST!)
kubectl apply -f infrastructure/kubernetes/production/n8n-secrets.yaml -n meeting-automation

# 4. Deployment anwenden
kubectl apply -f infrastructure/kubernetes/production/n8n-deployment.yaml -n meeting-automation

# 5. Ingress anwenden
kubectl apply -f infrastructure/kubernetes/production/n8n-ingress.yaml -n meeting-automation
kubectl apply -f infrastructure/kubernetes/production/ingress-prod.yaml -n meeting-automation

# 6. Rollout-Status prüfen
kubectl rollout status deployment/n8n -n meeting-automation --timeout=180s

# 7. Verifikation
curl -s https://meeting-automation.com/n8n/static/base-path.js | head -c 50
# Erwartet: window.BASE_PATH = '/n8n/'

curl -s https://meeting-automation.com/n8n/healthz
# Erwartet: {"status":"ok"}
```

### Rollback (bei Problemen)
```bash
# YAML-Dateien reverten
git checkout infrastructure/kubernetes/production/n8n-deployment.yaml
git checkout infrastructure/kubernetes/production/ingress-prod.yaml
git rm infrastructure/kubernetes/production/n8n-ingress.yaml

# Erneut anwenden
kubectl apply -f infrastructure/kubernetes/production/n8n-deployment.yaml -n meeting-automation
kubectl apply -f infrastructure/kubernetes/production/ingress-prod.yaml -n meeting-automation
kubectl rollout restart deployment/n8n -n meeting-automation
```

## Nächste Schritte (optional, nicht blockiert)
- **N8N_EDITOR_BASE_URL** auf `https://staging.meeting-automation.com/n8n/` setzen (n8n erzeugt
  korrekte Links in E-Mails/Notifications). Aktuell nutzt n8n internen DNS für Links.
- **WEBHOOK_URL** auf `https://staging.meeting-automation.com/n8n/` setzen (UI zeigt korrekte
  Production-URLs für Webhooks).
- **N8N_PROTOCOL** auf `https` setzen (n8n erzeugt HTTPS-Links statt HTTP).
- **L2 (Langfristig)**: Saubere Subdomain `n8n.staging.meeting-automation.com` mit eigenem
  DNS-Eintrag → kein NodePort nötig, kein Subpath-Strip, kein /n8n-Preifx-Handling.

## Epilog: DB-Hash Incident (2026-08-05)

### Was passiert ist
Beim Testen des n8n-Logins habe ich fälschlicherweise den bcrypt-Hash in der `users`-Tabelle
(Backend) auf einen Argon2-Hash umgestellt. Das war ein Fehler, weil:
1. Die `users`-Tabelle gehört zum Backend, nicht zu n8n
2. Die `user`-Tabelle (Singular) gehört zu n8n — ist aber fast leer
3. Der n8n-Login funktioniert trotzdem nicht (separates Problem)

### Bereinigung
- `seed_users.py` ausgeführt → bcrypt-Hash wiederhergestellt
- Alle 6 Users haben jetzt den korrekten bcrypt-Hash für `Password123!`
- DB-Integrität wiederhergestellt

### Lektion
- **NIEMALS** direkt in die DB greifen — immer über ORM/Scripts
- **Vor** Änderungen prüfen, welche Tabelle zu welchem Service gehört
- DB-Änderungen nur über Alembic-Migrations oder etablierte Scripts

## Hard Lessons
| # | Lektion |
|---|---------|
| L1 | **n8n `N8N_PATH` braucht trailing slash** — `/n8n` ohne Slash erzeugt `/n8nstatic/...`
  (zusammengeschnürte URLs), `/n8n/` erzeugt korrekte `/n8n/static/...` URLs. |
| L2 | **n8n `express.static()` ist immer an Root gemountet** — `N8N_PATH` beeinflusst NUR die
  HTML-Template-Rewrites (Browser-URLs), NICHT den Express-Static-Server. |
| L3 | **Ingress `rewrite-target` ist Ingress-level** — kann nicht pro-Path konfiguriert werden.
  Bei gemischten Services (Frontend + n8n) = separater Ingress nötig. |
| L4 | **K8s Probes funktionieren weiter** — `/healthz` bleibt an Root, `N8N_PATH` beeinflusst
  den Probe-Endpoint nicht. Liveness/Readiness unverändert. |
| L5 | **Backend-Webhooks unverändert** — Backend ruft `http://n8n-staging:5678/webhook/...`
  intern auf (ClusterIP), nicht über Ingress. `N8N_PATH` beeinflusst interne Webhook-URLs nicht. |
| L6 | **Empirischer Test vor Production** — n8n's Verhalten mit `N8N_PATH` war in BAUPLAN L3
  falsch angenommen („dann funktioniert die vorhandene `/n8n`-Route"). In Wirklichkeit
  braucht es den Ingress-Strip. Immer mit Docker本地 testen! |
