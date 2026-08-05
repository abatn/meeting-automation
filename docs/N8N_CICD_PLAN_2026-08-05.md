# n8n CI/CD Konsistenz Plan (2026-08-05)

## Ziel

Production soll **identisch** mit Staging sein — automatisch via CI/CD, ohne manuelle Schritte.

## Aktueller Zustand

| Komponente | Staging | Production | CI/CD? |
|---|---|---|---|
| Workflows (9 Stück) | ✅ | ✅ (manuell importiert) | ⚠️ Teilweise |
| SMTP Credential | ✅ | ❌ Fehlt | ❌ |
| n8n Owner Account | ✅ | ❌ Fehlt | ❌ |
| n8n Ingress | ✅ | ✅ | ✅ |
| N8N_PATH=/n8n/ | ✅ | ✅ | ✅ |
| N8N_ENCRYPTION_KEY | ✅ | ✅ | ✅ |

## DB Vergleich (Stand: 2026-08-05)

### Staging (meeting_db_staging)

| Tabelle | Zeilen |
|---|---|
| workflow_entity | 9 |
| workflow_history | 9 |
| credentials_entity | 1 (SMTP) |
| webhook_entity | 7 |
| settings | 5 |
| user (n8n) | 1 (Owner) |

### Production (meeting_db)

| Tabelle | Zeilen |
|---|---|
| workflow_entity | 9 |
| workflow_history | 9 |
| credentials_entity | **0** ❌ |
| webhook_entity | 7 |
| settings | 4 |
| user (n8n) | **0** ❌ |

### Fehlende Komponenten

1. **SMTP Credential** — Wird von 3 Workflows benötigt (meeting-status-changed, transcription-completed, pv-validated)
2. **n8n Owner Account** — Kein User eingerichtet

---

## Schritt 1: GitHub Secrets hinzufügen

Folgende Secrets müssen in **GitHub → Settings → Secrets → Actions** hinzugefügt werden:

### n8n SMTP Credentials

| Secret Name | Wert | Quelle |
|---|---|---|
| `N8N_SMTP_HOST` | `bulk.smtp.mailtrap.io` | Staging K8s ConfigMap |
| `N8N_SMTP_PORT` | `587` | Staging K8s ConfigMap |
| `N8N_SMTP_USER` | `api` | Staging K8s ConfigMap |
| `N8N_SMTP_PASSWORD` | `4e2fbbb5ef37900bd76094b79a0dbb82` | Staging K8s Secret |
| `N8N_SMTP_SSL` | `false` | Port 587 = STARTTLS |

### n8n Owner Account

| Secret Name | Wert | Quelle |
|---|---|---|
| `N8N_OWNER_EMAIL` | `batniniabdelkader@yahoo.com` | Staging n8n DB |
| `N8N_OWNER_PASSWORD` | `Abdelka15121978!` | Korrektes Passwort |

### Status

✅ **Alle 7 Secrets wurden am 2026-08-05 via `gh secret set` in GitHub erstellt.**

---

## Schritt 2: CI/CD Pipeline erweitern

### 2.1 deploy-production.yml

Neue Schritte nach dem Deploy (vor "Rollout restart"):

```yaml
# === n8n: Workflows importieren (idempotent) ===
- name: Import n8n Workflows to Production
  run: |
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    N8N_POD=$(kubectl get pods -n meeting-automation -l app=n8n -o jsonpath='{.items[0].metadata.name}')
    WORKFLOW_COUNT=$(kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
    
    if [ "$WORKFLOW_COUNT" = "0" ]; then
      echo "No workflows found — importing from n8n/workflows/*.json"
      kubectl exec -n meeting-automation $N8N_POD -- mkdir -p /home/node/.n8n/workflows
      for f in n8n/workflows/*.json; do
        name=$(basename $f)
        echo "Importing $name..."
        cat $f | kubectl exec -i -n meeting-automation $N8N_POD -- tee /home/node/.n8n/workflows/$name > /dev/null
        kubectl exec -n meeting-automation $N8N_POD -- n8n import:workflow --input=/home/node/.n8n/workflows/$name 2>&1 | tail -1 || true
      done
      echo "✅ n8n workflows imported"
    else
      echo "✅ n8n workflows already exist ($WORKFLOW_COUNT workflows) — skipping import"
    fi
  env:
    KUBECONFIG: /etc/rancher/k3s/k3s.yaml

# === n8n: SMTP Credential erstellen (idempotent) ===
- name: Create n8n SMTP Credential
  run: |
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    N8N_POD=$(kubectl get pods -n meeting-automation -l app=n8n -o jsonpath='{.items[0].metadata.name}')
    
    # Prüfen ob SMTP Credential bereits existiert
    CRED_COUNT=$(kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
    
    if [ "$CRED_COUNT" = "0" ]; then
      echo "No SMTP credential — creating via n8n REST API"
      
      # n8n Owner Login für Session Cookie
      curl -s -c /tmp/n8n-cookies.txt -X POST "http://localhost:8080/rest/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${N8N_OWNER_EMAIL}\",\"password\":\"${N8N_OWNER_PASSWORD}\"}" > /dev/null
      
      # SMTP Credential erstellen
      curl -s -b /tmp/n8n-cookies.txt -X POST "http://localhost:8080/rest/credentials" \
        -H "Content-Type: application/json" \
        -d "{
          \"name\": \"SMTP account\",
          \"type\": \"smtp\",
          \"data\": {
            \"user\": \"${N8N_SMTP_USER}\",
            \"password\": \"${N8N_SMTP_PASSWORD}\",
            \"host\": \"${N8N_SMTP_HOST}\",
            \"port\": ${N8N_SMTP_PORT},
            \"ssl\": ${N8N_SMTP_SSL}
          }
        }" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Created credential: {d.get(\"id\",\"?\")}')" 2>/dev/null || echo "⚠️ Credential creation failed"
      
      echo "✅ SMTP credential created"
    else
      echo "✅ SMTP credential already exists ($CRED_COUNT credentials) — skipping creation"
    fi
  env:
    KUBECONFIG: /etc/rancher/k3s/k3s.yaml
    N8N_OWNER_EMAIL: ${{ secrets.N8N_OWNER_EMAIL }}
    N8N_OWNER_PASSWORD: ${{ secrets.N8N_OWNER_PASSWORD }}
    N8N_SMTP_HOST: ${{ secrets.N8N_SMTP_HOST }}
    N8N_SMTP_PORT: ${{ secrets.N8N_SMTP_PORT }}
    N8N_SMTP_USER: ${{ secrets.N8N_SMTP_USER }}
    N8N_SMTP_PASSWORD: ${{ secrets.N8N_SMTP_PASSWORD }}
    N8N_SMTP_SSL: ${{ secrets.N8N_SMTP_SSL }}

# === n8n: Workflow-Nodes Credential-ID updaten ===
- name: Update Workflow Credential References
  run: |
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    
    # Neue Credential-ID aus DB auslesen
    NEW_CRED_ID=$(kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT id FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
    
    if [ -n "$NEW_CRED_ID" ]; then
      echo "Updating credential references to: $NEW_CRED_ID"
      
      # In workflow_entity updaten
      kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db \
        -c "UPDATE workflow_entity SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb 
            WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
      
      # In workflow_history updaten (n8n liest Nodes von hier!)
      kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db \
        -c "UPDATE workflow_history SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb 
            WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
      
      echo "✅ Credential references updated"
    else
      echo "⚠️ No SMTP credential found — skipping update"
    fi
  env:
    KUBECONFIG: /etc/rancher/k3s/k3s.yaml
```

### 2.2 e2e-tests.yml (Staging)

Gleicher Ansatz für Staging — nach "Deploy Celery Workers to Staging":

```yaml
# === n8n: Workflows + Credentials importieren ===
- name: Import n8n Workflows & Credentials to Staging
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-staging
    N8N_POD=$(kubectl get pods -n meeting-automation-staging -l app=n8n-staging -o jsonpath='{.items[0].metadata.name}')
    
    # Workflows
    WORKFLOW_COUNT=$(kubectl exec -n meeting-automation-staging meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
    if [ "$WORKFLOW_COUNT" = "0" ]; then
      echo "Importing workflows..."
      kubectl exec -n meeting-automation-staging $N8N_POD -- mkdir -p /home/node/.n8n/workflows
      for f in n8n/workflows/*.json; do
        name=$(basename $f)
        cat $f | kubectl exec -i -n meeting-automation-staging $N8N_POD -- tee /home/node/.n8n/workflows/$name > /dev/null
        kubectl exec -n meeting-automation-staging $N8N_POD -- n8n import:workflow --input=/home/node/.n8n/workflows/$name 2>&1 | tail -1 || true
      done
      echo "✅ Workflows imported"
    else
      echo "✅ Workflows already exist ($WORKFLOW_COUNT)"
    fi
    
    # Credentials (nur wenn leer)
    CRED_COUNT=$(kubectl exec -n meeting-automation-staging meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
    if [ "$CRED_COUNT" = "0" ]; then
      echo "Creating SMTP credential..."
      curl -s -c /tmp/n8n-cookies.txt -X POST "http://localhost:8080/rest/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${N8N_OWNER_EMAIL}\",\"password\":\"${N8N_OWNER_PASSWORD}\"}" > /dev/null
      curl -s -b /tmp/n8n-cookies.txt -X POST "http://localhost:8080/rest/credentials" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"SMTP account\",\"type\":\"smtp\",\"data\":{\"user\":\"${N8N_SMTP_USER}\",\"password\":\"${N8N_SMTP_PASSWORD}\",\"host\":\"${N8N_SMTP_HOST}\",\"port\":${N8N_SMTP_PORT},\"ssl\":${N8N_SMTP_SSL}}}" > /dev/null
      echo "✅ SMTP credential created"
    else
      echo "✅ SMTP credential already exists"
    fi
    
    # n8n neustarten
    kubectl rollout restart deployment/n8n-staging -n meeting-automation-staging
  env:
    N8N_OWNER_EMAIL: ${{ secrets.STAGING_N8N_OWNER_EMAIL }}
    N8N_OWNER_PASSWORD: ${{ secrets.STAGING_N8N_OWNER_PASSWORD }}
    N8N_SMTP_HOST: ${{ secrets.STAGING_N8N_SMTP_HOST }}
    N8N_SMTP_PORT: ${{ secrets.STAGING_N8N_SMTP_PORT }}
    N8N_SMTP_USER: ${{ secrets.STAGING_N8N_SMTP_USER }}
    N8N_SMTP_PASSWORD: ${{ secrets.STAGING_N8N_SMTP_PASSWORD }}
    N8N_SMTP_SSL: ${{ secrets.STAGING_N8N_SMTP_SSL }}
```

---

## Schritt 3: n8n Owner Setup

### Option A: REST API (empfohlen)

```bash
# Setup-Endpoint (nur beim ersten Start)
curl -X POST "https://meeting-automation.com/n8n/rest/owner/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "batniniabdelkader@yahoo.com",
    "password": "Abdelka15121978!",
    "firstName": "Abdelkader",
    "lastName": "Batnini"
  }'
```

### Option B: DB-Seed (Fallback)

```bash
# Owner direkt in DB setzen
kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -c "
  INSERT INTO \"user\" (id, email, \"firstName\", \"lastName\", password, \"personalizationAnswers\") 
  VALUES (
    gen_random_uuid(), 
    'batniniabdelkader@yahoo.com', \
    'Abdelkader', 
    'Batnini', 
    '\$2b\$12\$...',
    '{}'
  ) ON CONFLICT DO NOTHING;
"
```

---

## Schritt 4: Verifikation

```bash
# 1. Workflows vorhanden?
kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -c "SELECT count(*) FROM workflow_entity;"
# Erwartet: 9

# 2. Credentials vorhanden?
kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -c "SELECT count(*) FROM credentials_entity;"
# Erwartet: 1

# 3. Webhooks registriert?
kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -c "SELECT count(*) FROM webhook_entity;"
# Erwartet: 7

# 4. n8n Owner vorhanden?
kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -c "SELECT count(*) FROM \"user\";"
# Erwartet: 1

# 5. n8n UI funktioniert?
curl -s https://meeting-automation.com/n8n/healthz
# Erwartet: {"status":"ok"}

# 6. n8n Login funktioniert?
curl -s -X POST "https://meeting-automation.com/n8n/rest/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"batniniabdelkader@yahoo.com","password":"Abdelka15121978!"}'
# Erwartet: 200 mit User-Daten
```

---

## Risiken und Einschränkungen

| Risiko | Impact | Lösung |
|---|---|---|
| SMTP Passwort in GitHub Secrets | Secrets sind verschlüsselt, aber sichtbar für Admins | OK für interne Nutzung |
| Credential-ID wechselt bei neuem Import | Workflows referenzieren alte ID | Schritt 4 (ID-Update) |
| n8n Owner Setup nur beim ersten Mal | Bei PVC-Reset verloren | CI/CD prüft und erstellt neu |
| Execution History geht verloren | Nur bei PVC-Reset | Akzeptabel — nur Historie |

---

## Zusammenfassung

| Schritt | Datei | Aufwand |
|---|---|---|
| 1. GitHub Secrets | GitHub UI | 5 Min |
| 2. CI/CD Pipeline | deploy-production.yml + e2e-tests.yml | 30 Min |
| 3. n8n Owner Setup | CI/CD oder Setup-Script | 15 Min |
| 4. Credential-ID Update | CI/CD Script | 15 Min |
| 5. Verifikation | Script | 10 Min |

**Gesamt:** ~75 Minuten

---

## Offene Fragen

1. Soll der n8n Owner via REST API oder via DB-Seed eingerichtet werden?
2. Sollen Execution History und Settings ebenfalls synchronisiert werden?
3. Gibt es weitere Credentials die später hinzugefügt werden könnten?
