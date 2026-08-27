# OnlyOffice Production Fix — Rollback-Plan

**Datum:** 2026-08-27
**Cluster:** Production (169.58.83.32)
**Namespace:** meeting-automation

---

## Problem

OnlyOffice Editor funktioniert auf Production nicht:
- `/web-apps/apps/documenteditor/main/index.html` → Redirect zu `/9.4.0-{hash}/web-apps/...`
- `/9.4.0-{hash}/web-apps/...` → Frontend (React HTML) statt OnlyOffice Editor
- Ursache: Production Frontend-Nginx-Config fehlt 3 Location-Blöcke + X-Forwarded-Proto Headers

## Ursache

Production `frontend-nginx-config.yaml` ist eine vereinfachte Version von Staging. Es fehlen:

| Feature | Staging | Production |
|---------|---------|------------|
| `location ~ ^/[0-9]+\.[0-9]+\.[0-9]+[-.]` | ✅ | ❌ |
| `location /cache/` | ✅ | ❌ |
| `location /healthcheck` | ✅ | ❌ |
| `proxy_set_header X-Forwarded-Proto $scheme` (in /web-apps/) | ✅ | ❌ |
| `proxy_set_header X-Forwarded-Host $http_host` (in /web-apps/) | ✅ | ❌ |
| `proxy_set_header X-Forwarded-Prefix ""` (in /web-apps/) | ✅ | ❌ |

---

## Schritte mit Before/After und Rollback

> **Hinweis:** Schritte 5-6 (TLS) wurden als nicht nötig identifiziert — Cloudflare läuft im Flexible SSL-Modus.

### Schritt 1: Frontend-Nginx ConfigMap (Kritischster Fix)

**Ziel:** Production Frontend-Nginx bekommt alle fehlenden Location-Blöcke aus Staging.

**Before:**
```nginx
location /web-apps/ {
    proxy_pass http://onlyoffice.meeting-automation.svc.cluster.local:80;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
}
# Kein /cache/, keine versionierte Location, kein /healthcheck
```

**After:**
```nginx
location /web-apps/ {
    proxy_pass http://onlyoffice.meeting-automation.svc.cluster.local:80;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Prefix "";
    proxy_read_timeout 600s;
}

location /cache/ {
    proxy_pass http://onlyoffice.meeting-automation.svc.cluster.local:80;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 600s;
}

location ~ ^/[0-9]+\.[0-9]+\.[0-9]+[-.] {
    proxy_pass http://onlyoffice.meeting-automation.svc.cluster.local:80;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Prefix "";
    proxy_read_timeout 600s;
}

location /healthcheck {
    proxy_pass http://onlyoffice.meeting-automation.svc.cluster.local:80;
}
```

**Befehl:**
```bash
# Lokale Datei zuerst auf Server kopieren ( --from-file erwartet/nginx.conf, nicht YAML-Wrapper)
sed -n '8,115p' infrastructure/kubernetes/production/frontend-nginx-config.yaml | \
  ssh root@169.58.83.32 'cat > /tmp/default.conf'

ssh root@169.58.83.32 "kubectl create configmap frontend-nginx-config \
  -n meeting-automation \
  --from-file=default.conf=/tmp/default.conf \
  --dry-run=client -o yaml | kubectl apply -f -"

ssh root@169.58.83.32 "kubectl rollout restart deployment/frontend -n meeting-automation"
```

**Rollback:**
```bash
ssh root@169.58.83.32 "kubectl apply -f /tmp/onlyoffice-backup-2026-08-27/frontend-nginx-config-backup.yaml"
ssh root@169.58.83.32 "kubectl rollout restart deployment/frontend -n meeting-automation"
```

**Verifikation:**
```bash
ssh root@169.58.83.32 "kubectl get configmap frontend-nginx-config -n meeting-automation -o jsonpath='{.data.default\.conf}' | grep 'location'"
# Erwartung: = /index.html, /, /assets/, /api/v1/websockets/, /web-apps/, /cache/, ~ ^/[0-9]+, /healthcheck, /api/
```

---

### Schritt 2: ConfigMap onlyoffice-proxy-headers

**Ziel:** Definiert welche Headers ingress-nginx an OnlyOffice weiterleitet.

**Before:** ConfigMap existiert nicht.

**After:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: onlyoffice-proxy-headers
  namespace: ingress-automation
data:
  X-Forwarded-Proto: "https"
```

**Befehl:**
```bash
# Namespace erstellen falls nicht vorhanden
ssh root@169.58.83.32 "kubectl create namespace ingress-automation --dry-run=client -o yaml | kubectl apply -f -"

ssh root@169.58.83.32 "kubectl create configmap onlyoffice-proxy-headers \
  -n ingress-automation \
  --from-literal=X-Forwarded-Proto=https \
  --dry-run=client -o yaml | kubectl apply -f -"
```

**Rollback:**
```bash
ssh root@169.58.83.32 "kubectl delete configmap onlyoffice-proxy-headers -n ingress-automation"
```

**Verifikation:**
```bash
ssh root@169.58.83.32 "kubectl get configmap onlyoffice-proxy-headers -n ingress-automation -o yaml"
```

---

### Schritt 3: Annotation proxy-set-headers

**Ziel:** Verbindet den Ingress mit der ConfigMap aus Schritt 2.

**Before:** Keine `proxy-set-headers` Annotation.

**After:**
```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-set-headers: "ingress-automation/onlyoffice-proxy-headers"
```

**Befehl:**
```bash
ssh root@169.58.83.32 "kubectl annotate ingress meeting-production \
  -n meeting-automation \
  nginx.ingress.kubernetes.io/proxy-set-headers=ingress-automation/onlyoffice-proxy-headers \
  --overwrite"
```

**Rollback:**
```bash
ssh root@169.58.83.32 "kubectl annotate ingress meeting-production \
  -n meeting-automation \
  nginx.ingress.kubernetes.io/proxy-set-headers-"
```

**Verifikation:**
```bash
ssh root@169.58.83.32 "kubectl get ingress meeting-production -n meeting-automation -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/proxy-set-headers}'"
# Erwartung: ingress-automation/onlyoffice-proxy-headers
```

---

### Schritt 4: ingress-nginx Controller ConfigMap

**Ziel:** Aktiviert `use-forwarded-headers` damit ingress-nginx X-Forwarded-Proto von Cloudflare verarbeitet.

**Before:** ConfigMap `ingress-nginx-controller` hat keine `data` Section.

**After:**
```yaml
data:
  use-forwarded-headers: "true"
  compute-full-forwarded-for: "true"
```

**Befehl:**
```bash
ssh root@169.58.83.32 "kubectl patch configmap ingress-nginx-controller \
  -n ingress-nginx \
  --type merge \
  -p '{\"data\":{\"use-forwarded-headers\":\"true\",\"compute-full-forwarded-for\":\"true\"}}'"
```

**Rollback:**
```bash
ssh root@169.58.83.32 "kubectl patch configmap ingress-nginx-controller \
  -n ingress-nginx \
  --type json \
  -p '[{\"op\": \"remove\", \"/path\": \"/data/use-forwarded-headers\"},{\"op\": \"remove\", \"/path\": \"/data/compute-full-forwarded-for\"}]'"
```

**Verifikation:**
```bash
ssh root@169.58.83.32 "kubectl get configmap ingress-nginx-controller -n ingress-nginx -o jsonpath='{.data}'"
# Erwartung: {"compute-full-forwarded-for":"true","use-forwarded-headers":"true"}
```

---

### Schritt 5 & 6: TLS — NICHT NÖTIG (Cloudflare Flexible Mode)

**Feststellung:** Cloudflare ist im **Flexible** SSL-Modus:
- TLS wird am Cloudflare Edge terminiert
- Origin wird via HTTP (Port 80) angesprochen
- TLS Secret `production-tls` wird NICHT benötigt
- `spec.tls` im Ingress wird NICHT benötigt

**Evidence:**
- `curl -sk https://meeting-automation.com/` → 200 OK mit `cf-ray` Header
- Origin antwortet nicht auf HTTPS (404 auf Port 443)
- Origin antwortet via HTTP mit Host-Header (308 Redirect → Ingress)

**Wenn Cloudflare später auf Full (Strict) umgestellt wird:**
1. Cloudflare Dashboard → SSL/TLS → Origin Server → Create Certificate
2. `kubectl create secret tls production-tls -n meeting-automation --cert=cert.pem --key=key.pem`
3. TLS-Sektion zum Ingress hinzufügen (siehe Rollback-Dokument für Beispiel)

---

## Verifikation nach allen Schritten

```bash
# 1. Frontend-Nginx ConfigMap (9 Location-Blöcke)
ssh root@169.58.83.32 "kubectl get configmap frontend-nginx-config -n meeting-automation -o jsonpath='{.data.default\.conf}' | grep 'location'"
# Erwartung: = /index.html, /, /assets/, /api/v1/websockets/, /web-apps/, /cache/, ~ ^/[0-9]+, /healthcheck, /api/

# 2. onlyoffice-proxy-headers ConfigMap (in ingress-automation)
ssh root@169.58.83.32 "kubectl get configmap onlyoffice-proxy-headers -n ingress-automation -o yaml"

# 3. Annotation proxy-set-headers
ssh root@169.58.83.32 "kubectl get ingress meeting-production -n meeting-automation -o jsonpath='{.metadata.annotations}'"
# Erwartung: "nginx.ingress.kubernetes.io/proxy-set-headers":"ingress-automation/onlyoffice-proxy-headers"

# 4. ingress-nginx use-forwarded-headers
ssh root@169.58.83.32 "kubectl get configmap ingress-nginx-controller -n ingress-nginx -o jsonpath='{.data}'"
# Erwartung: {"compute-full-forwarded-for":"true","use-forwarded-headers":"true"}

# 5. OnlyOffice Editor testen
curl -sk 'https://meeting-automation.com/web-apps/apps/documenteditor/main/index.html' -L | grep '<title>'
# Erwartung: <title>ONLYOFFICE Document Editor</title>

# 6. Redirect-Header testen (X-Forwarded-Proto → https)
curl -sk 'https://meeting-automation.com/web-apps/apps/documenteditor/main/index.html' -D- | grep -E 'location:|302'
# Erwartung: location: https://meeting-automation.com/9.4.0-{hash}/web-apps/...

# 7. Frontend-Pod Status
ssh root@169.58.83.32 "kubectl get pods -n meeting-automation -l app=frontend"
# Erwartung: 1/1 Running, kein CrashLoopBackOff
```

## Full Rollback (alle Schritte rückgängig)

```bash
# 1. Frontend-Nginx ConfigMap wiederherstellen
ssh root@169.58.83.32 "kubectl apply -f /tmp/onlyoffice-backup-2026-08-27/frontend-nginx-config-backup.yaml"
ssh root@169.58.83.32 "kubectl rollout restart deployment/frontend -n meeting-automation"

# 2. onlyoffice-proxy-headers löschen
ssh root@169.58.83.32 "kubectl delete configmap onlyoffice-proxy-headers -n ingress-automation"

# 3. Annotation entfernen
ssh root@169.58.83.32 "kubectl annotate ingress meeting-production -n meeting-automation nginx.ingress.kubernetes.io/proxy-set-headers-"

# 4. use-forwarded-headers entfernen
ssh root@169.58.83.32 "kubectl patch configmap ingress-nginx-controller -n ingress-nginx --type json -p '[{\"op\": \"remove\", \"/path\": \"/data/use-forwarded-headers\"}]'"

# 5. ingress-nginx neu starten
ssh root@169.58.83.32 "kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx"

# 6. Frontend-Pod prüfen
ssh root@169.58.83.32 "kubectl get pods -n meeting-automation -l app=frontend"
```

## Risiken

| Risiko | Auswirkung | Gegenmaßnahme |
|--------|------------|---------------|
| Frontend-Pod Crash nach ConfigMap-Update | Frontend nicht erreichbar | Frontend-ConfigMap wiederherstellen + rollout restart |
| ingress-nginx Reload-Verzögerung | Headers werden erst nach ~1min wirksam | ingress-nginx Pod neu starten |
| Cloudflare ändert SSL-Modus auf Full | Origin braucht TLS Certificate | Cloudflare Origin Certificate erstellen + TLS Secret anlegen |
| proxy-set-headers ConfigMap im falschen Namespace | OnlyOffice bekommt kein X-Forwarded-Proto | ConfigMap in ingress-automation (nicht ingress-nginx) |

## Abhängigkeiten

```
Schritt 1 (Frontend-Nginx) ── unabhängig ── Schritt 2 (onlyoffice-proxy-headers)
Schritt 2 ── abhängig von Schritt 3 (Annotation)
Schritt 4 (use-forwarded-headers) ── unabhängig
Schritte 5-6 (TLS) ── nicht nötig (Cloudflare Flexible Mode)
```
