# GitHub Environments Setup — Schritt-für-Schritt Anleitung

> **Erstellt**: 2026-08-07
> **Status**: ⏳ MANUELL AUSFÜHREN (GitHub UI)
> **Voraussetzung**: GitHub Repository `meeting-automation` (Owner: `batnini`)

---

## 1. Übersicht

| Environment | Approval | Zweck |
|-------------|----------|-------|
| **staging** | Keiner (auto) | Automatischer Deploy nach CI |
| **production** | `required_reviewers` | Manueller Deploy mit Genehmigung |

---

## 2. Environment: `staging`

### 2.1 Erstellen

```
GitHub → Settings → Environments → New environment
Name: staging
```

### 2.2 Protection Rules

```
Deployment branches:
  ☑ Selected branches
  → Add: "main"

Required reviewers:
  ☐ DEAKTIVIERT (staging deployt automatisch)
```

### 2.3 Secrets hinzufügen

**Button**: "Add secret" (pro Secret einzeln)

| Secret Name | Wert | Quelle |
|-------------|------|--------|
| `KUBE_CONFIG_STAGING` | *(Inhalt von `kubeconfig-staging.txt`)* | Staging Cluster |
| `STAGING_E2E_USER_EMAIL` | `test@example.com` | E2E Test User |
| `STAGING_E2E_USER_PASSWORD` | `test_password_123` | E2E Test User |
| `MISTRAL_API_KEY_STAGING` | *(Mistral API Key)* | Mistral Dashboard |
| `GLADIA_API_KEY_STAGING` | *(Gladia API Key)* | Gladia Dashboard |
| `STAGING_N8N_OWNER_EMAIL` | `batniniabdelkader@yahoo.com` | n8n Owner |
| `STAGING_N8N_OWNER_PASSWORD` | `Abdelka15121978!` | n8n Owner |
| `STAGING_N8N_SMTP_HOST` | `bulk.smtp.mailtrap.io` | SMTP Config |
| `STAGING_N8N_SMTP_PORT` | `587` | SMTP Config |
| `STAGING_N8N_SMTP_USER` | `api` | SMTP Config |
| `STAGING_N8N_SMTP_PASSWORD` | `4e2fbbb5ef37900bd76094b79a0dbb82` | SMTP Config |
| `STAGING_N8N_SMTP_SSL` | `false` | SMTP Config |
| `DOCKERHUB_TOKEN` | *(Docker Hub Access Token)* | Docker Hub |

### 2.4 Variables (optional)

| Variable Name | Wert | Zweck |
|---------------|------|-------|
| `KUBECONFIG_PATH` | `kubeconfig-staging` | Pfad zur kubeconfig Datei |

---

## 3. Environment: `production`

### 3.1 Erstellen

```
GitHub → Settings → Environments → New environment
Name: production
```

### 3.2 Protection Rules

```
Deployment branches:
  ☑ Selected branches
  → Add: "main"

Required reviewers:
  ☑ AKTIVIERT
  → Reviewer hinzufügen: [mindestens 1 Team-Member]
  
Wait timer:
  ☐ 0 minutes (oder 5-10 min für extra Sicherheit)
```

### 3.3 Secrets hinzufügen

**Button**: "Add secret" (pro Secret einzeln)

| Secret Name | Wert | Quelle |
|-------------|------|--------|
| `KUBE_CONFIG_PRODUCTION` | *(Inhalt von `/etc/rancher/k3s/k3s.yaml`)* | Production Cluster |
| `DOCKERHUB_TOKEN` | *(Docker Hub Access Token)* | Docker Hub |
| `DOCKERHUB_USERNAME` | `batnini` | Docker Hub |
| `CONTABO_SSH_KEY` | *(SSH Private Key für Contabo)* | Contabo Server |
| `MISTRAL_API_KEY` | *(Mistral API Key)* | Mistral Dashboard |
| `GLADIA_API_KEY` | *(Gladia API Key)* | Gladia Dashboard |
| `N8N_OWNER_EMAIL` | `batniniabdelkader@yahoo.com` | n8n Owner |
| `N8N_OWNER_PASSWORD` | `Abdelka15121978!` | n8n Owner |
| `N8N_SMTP_HOST` | `bulk.smtp.mailtrap.io` | SMTP Config |
| `N8N_SMTP_PORT` | `587` | SMTP Config |
| `N8N_SMTP_USER` | `api` | SMTP Config |
| `N8N_SMTP_PASSWORD` | `4e2fbbb5ef37900bd76094b79a0dbb82` | SMTP Config |
| `N8N_SMTP_SSL` | `false` | SMTP Config |

---

## 4. GitHub Secrets (Repository-level)

Diese Secrets sind **repository-wide** (nicht pro Environment):

| Secret Name | Wert | Verwendet in |
|-------------|------|--------------|
| `ENCRYPTION_KEY` | *(Fernet Key)* | Backend Tests |
| `TOTP_ENCRYPTION_KEY` | *(TOTP Key)* | Backend Tests |
| `SECRET_KEY` | *(JWT Secret)* | Backend Tests |

---

## 5. Überprüfung

### 5.1 Environments prüfen

```
GitHub → Settings → Environments

Erwartet:
  staging    ✅ (keine Reviewers, Branch: main)
  production ✅ (1+ Reviewers, Branch: main)
```

### 5.2 Secrets prüfen

```
GitHub → Settings → Environments → staging → Secrets

Erwartet: 13 Secrets sichtbar
```

### 5.3 Workflow-Verknüpfung prüfen

```
.github/workflows/ci.yml          → Kein Environment (nur Tests)
.github/workflows/deploy-staging.yml   → environment: staging
.github/workflows/deploy-production.yml → environment: production
```

---

## 6. Test-Flow nach Setup

### 6.1 Staging Auto-Deploy testen

```bash
# 1. Code ändern
echo "# test" >> README.md
git add README.md
git commit -m "test: CI/CD auto-deploy staging"
git push origin main

# 2. GitHub Actions beobachten
# → ci.yml startet (Tests + Build)
# → deploy-staging.yml startet (nach ci.yml Erfolg)
# → Staging wird deployed

# 3. Verifizieren
curl -s https://staging.meeting-automation.com/health
```

### 6.2 Production Manual Deploy testen

```bash
# 1. GitHub → Actions → Deploy Production → Run workflow
# 2. Inputs eingeben:
#    - image_tag: latest (oder ein SHA)
#    - confirm: yes
# 3. "Run workflow" klicken
# 4. GitHub zeigt "Waiting for review"
# 5. Team-Member genehmigt
# 6. Deploy startet
```

---

## 7. Troubleshooting

### 7.1 "Environment not found"

**Ursache**: Environment nicht erstellt oder falscher Name.

**Fix**:
```
GitHub → Settings → Environments → Prüfe Name ("staging" / "production")
```

### 7.2 "Secret not found"

**Ursache**: Secret nicht in der richtigen Environment hinterlegt.

**Fix**:
```
GitHub → Settings → Environments → [Environment] → Secrets → Prüfe Name
```

### 7.3 "Waiting for review" hängt

**Ursache**: Kein Reviewer zugewiesen oder Reviewer nicht erreichbar.

**Fix**:
```
GitHub → Settings → Environments → production → Required reviewers → Reviewer hinzufügen
```

### 7.4 Workflow erkennt SHA nicht

**Ursache**: `github.sha` stimmt nicht mit deploytem Image überein.

**Fix**: Manuell mit `workflow_dispatch` + korrektem Tag deployen.

---

## 8. Sicherheits-Hinweise

| Hinweis | Details |
|---------|---------|
| **Secrets sind verschlüsselt** | GitHub speichert Secrets verschlüsselt |
| **Secrets sind sichtbar für Admins** | Repository-Admins können Secrets lesen |
| **Secrets nicht im Log** | GitHub maskiert automatisch Secrets in Logs |
| **Production Approval** | Nur genehmigte Deployments erreichen Production |
| **Branch Protection** | Empfohlen: Branch Protection Rules für `main` |

---

## 9. Zusammenfassung

| Schritt | Aufwand | Wichtigkeit |
|---------|---------|-------------|
| 1. Environments erstellen | 5 Min | Pflicht |
| 2. Protection Rules setzen | 5 Min | Pflicht |
| 3. Secrets hinzufügen | 15 Min | Pflicht |
| 4. Testen (Staging Auto-Deploy) | 10 Min | Empfohlen |
| 5. Testen (Production Manual) | 10 Min | Empfohlen |
| **Gesamt** | **~45 Min** | |

---

**NÄCHSTER SCHRITT**: Secrets in GitHub UI eintragen (manuell, da Secrets nicht via API erstellt werden können).
