# Incident Report: deploy-production.yml exceeds GitHub 21K Expression Limit

**Datum:** 2026-08-16
**Dauer:** ~4 Stunden (17:20 → 21:30 UTC)
**Impact:** Production Deploys via API/CLI unmöglich
**Severity:** P2 (Production Deploy blockiert, aber kein Service-Ausfall)
**Status:** ✅ Behoben (`a1604e3e`)

---

## 1. Zusammenfassung

Die `deploy-production.yml` überschritt das GitHub Actions API-Limit von 21.000 Zeichen
für `workflow_dispatch`-Trigger. Jeder Deploy-Versuch über die API oder `gh workflow run`
scheiterte mit HTTP 422: `Exceeded max expression length 21000`.

**Root Cause:** Die Datei enthielt ein massives inline-SSH-Script (~500 Zeilen) das
alle Deploy-Logik in einem Block ausführte. Mit 30.957 Zeichen lag sie 50% über dem Limit.

**Lösung:** Shell-Scripte nach `scripts/deploy-prod/` ausgelagert (10 Dateien).
Die Workflow-Datei wurde von 30.957 auf 6.310 Zeichen reduziert.

---

## 2. Timeline

| Zeit (UTC) | Event | Beweis |
|---|---|---|
| 17:20 | Erster Deploy-Versuch mit `image_tag=91e8d540` | Deploy #31961311937 |
| 17:20 | **HTTP 422: Exceeded max expression length 21000** | GitHub API Response |
| 17:22 | 2. Versuch (kurze SHA) → gleiches Ergebnis | Deploy #31962184891 |
| 17:38 | 3. Versuch → gleiches Ergebnis | Deploy #31962500445 |
| 17:44 | 4. Versuch → gleiches Ergebnis | Deploy #31962500445 |
| 18:08 | Deploy mit `image_tag=latest` → Rollout Timeout (celery-worker min=0) | Deploy #31963684452 |
| 18:35 | Fix `477b2be2`: celery-worker Rollout-Skip | CI Pipeline ✅ |
| 21:07 | Deploy mit neuem Fix → **wieder HTTP 422** (File immer noch zu groß) | Deploy #31972532336 |
| 21:08 | Analyse: File = 30.957 Chars, Limit = 21.000 | `wc -c deploy-production.yml` |
| 21:18 | Fix: Shell-Scripte ausgelagert → File = 6.310 Chars | `e590e618` |
| 21:21 | Deploy mit neuem File → **SCP strip_components Fehler** | Deploy #31973261253 |
| 21:23 | SCP leer: `strip_components: 3` auf `scripts/deploy-prod/` (2 Komponenten) | Server: `/root/deploy-scripts/` leer |
| 21:28 | Fix: `strip_components: 3` → `2` | `a1604e3e` |
| 21:29 | Deploy getriggert → **✅ ERFOLGREICH** | Deploy #31973638381 |

---

## 3. Root Cause Analyse

### 3.1 Warum war die Datei so groß?

Die `deploy-production.yml` enthielt ein einzigesmassives SSH-Script in der
`Deploy to Contabo Production` Step:

```
Step: Deploy to Contabo Production (appleboy/ssh-action)
  └── script: |
        set -e
        # ~500 Zeilen Shell-Code inline:
        # - Image Pull (k3s ctr)
        # - Manifest Apply (kubectl apply)
        # - LiveKit Helm + Patches
        # - Velero Scope Check
        # - Longhorn Install
        # - KEDA Install + Test
        # - KEDA ScaledObjects
        # - System CronJobs
        # - Image-Cleanup
        # - k3s config.yaml
        # - Deploy Images + Rollout
        # - n8n Workflows + Owner + SMTP
        # - Smoke Tests
        # - k3s Restart
```

### 3.2 Warum war das nie sichtbar?

| Trigger-Typ | 21K Limit? | Staging | Production |
|---|---|---|---|
| `workflow_run` (CI auto-trigger) | ❌ **Nein** | ✅ Genutzt | ❌ Nie genutzt |
| `workflow_dispatch` (manuell) | ✅ **Ja** | ❌ Nie genutzt | ✅ Einzige Methode |

**Staging** wird via `workflow_dispatch` nie getriggert — es läuft automatisch
nach CI-Erfolg via `workflow_run`. Deshalb war das Limit nie erreichbar.

**Production** wird NUR via `workflow_dispatch` getriggert (manuell). Das
GitHub API-Limit von 21.000 Zeichen für Expressions wurde erst erreicht als
die Datei über die Zeit wuchs (Velero, KEDA, Celery-Rollout-Skip Fixes).

### 3.3 Zweiter Bug: `strip_components`

Die SCP-Action für `scripts/deploy-prod/` verwendete `strip_components: 3`:

```
source: "scripts/deploy-prod/"    # 2 Komponenten: scripts + deploy-prod
strip_components: 3               # Entfernt 3 Ebenen → nichts bleibt
```

**Ergebnis:** `/root/deploy-scripts/` auf dem Server war leer.
`deploy-all.sh` konnte nicht ausgeführt werden → `exit code 1`.

---

## 4. Lösung

### 4.1 Shell-Script-Auslagerung

10 Shell-Scripte in `scripts/deploy-prod/` erstellt:

| Datei | Zeilen | Zweck |
|---|---|---|
| `01-pull-images.sh` | 30 | k3s ctr image pull |
| `02-apply-manifests.sh` | 35 | kubectl apply |
| `03-deploy-livekit.sh` | 50 | Helm + Patches |
| `04-velero-scope-check.sh` | 40 | Scope Check + P3 Probes |
| `05-install-infra.sh` | 60 | Longhorn + KEDA + NetworkPolicy |
| `06-deploy-system.sh` | 45 | CronJobs + image-cleanup + k3s config |
| `07-deploy-apps.sh` | 40 | kubectl set image + rollout |
| `08-setup-n8n.sh` | 80 | Workflows + Owner + SMTP |
| `09-smoke-tests.sh` | 50 | Health Check |
| `deploy-all.sh` | 70 | Master-Orchestrierer |

### 4.2 Workflow-Refactoring

`deploy-production.yml` wurde umgeschrieben:

**Vorher (30.957 chars):**
```yaml
- name: Deploy to Contabo Production
  uses: appleboy/ssh-action@v1
  with:
    script: |
      set -e
      # ~500 Zeilen inline...
```

**Nachher (6.310 chars):**
```yaml
- name: Copy deploy scripts to Contabo
  uses: appleboy/scp-action@v0.1.7
  with:
    source: "scripts/deploy-prod/"
    target: "/root/deploy-scripts"
    strip_components: 2          # ← Korrigiert

- name: Deploy to Contabo Production
  uses: appleboy/ssh-action@v1
  with:
    script: |
      export TAG="${{ inputs.image_tag }}"
      export BACKEND_IMAGE="docker.io/batnini/meeting-automation-backend:$TAG"
      export FRONTEND_IMAGE="docker.io/batnini/meeting-automation-frontend:$TAG"
      chmod +x /root/deploy-scripts/*.sh
      bash /root/deploy-scripts/deploy-all.sh
```

---

## 5. Verifikation

| Test | Ergebnis |
|---|---|
| `wc -c deploy-production.yml` | 6.310 < 21.000 ✅ |
| YAML-Validierung | ✅ valid |
| API Dispatch (`curl POST`) | HTTP 204 (akzeptiert) ✅ |
| SCP nach Server | `/root/deploy-scripts/` = 10 Dateien ✅ |
| `deploy-all.sh` Ausführung | Exit 0 ✅ |
| Production Deploy | ✅ success (3m 5s) |
| Alle Pods Running | ✅ 15/15 |

---

## 6. Betroffene Dateien

| Datei | Änderung | Commit |
|---|---|---|
| `.github/workflows/deploy-production.yml` | 30.957 → 6.310 chars | `e590e618`, `a1604e3e` |
| `scripts/deploy-prod/*.sh` | 10 neue Dateien | `e590e618` |

---

## 7. Lektionen

### L1: GitHub 21K Expression-Limit für workflow_dispatch

GitHub Actions hat ein **hartes Limit von 21.000 Zeichen** für die Expression-Phase
von `workflow_dispatch`-Workflows. Dieses Limit gilt NICHT für:
- `workflow_run` (automatisch getriggert)
- `push`/`pull_request` Events

**Regel:** `workflow_dispatch`-Workflows müssen unter 21K Zeichen bleiben.
Große Shell-Scripts müssen in externe Dateien ausgelagert werden.

### L2: SCP `strip_components` muss zur Quell-Pfad-Tiefe passen

```
source: "scripts/deploy-prod/"    # 2 Komponenten
strip_components: 2               # Korrekt
strip_components: 3               # FALSCH → leeres Verzeichnis
```

**Regel:** `strip_components` = (Anzahl Pfad-Komponenten in `source`).

### L3: Staging ≠ Production Trigger-Typ

Staging (`workflow_run`) und Production (`workflow_dispatch`) haben
unterschiedliche Limits. Ein Problem das nur Production betrifft, ist
bei Staging nie sichtbar.

**Regel:** CI/CD-Probleme immer an beiden Clustern verifizieren.

### L4: Inline-Shell-Scripts in Workflows skalieren nicht

Eine Shell mit 500+ Zeilen in einer YAML-Datei ist:
- Schwer zu warten
- Schwer zu testen
- Anfällig für Limits

**Regel:** Shell-Scripte > 50 Zeilen in externe `.sh`-Dateien auslagern.

---

## 8. Offene Punkte

| # | Punkt | Status | Priorität |
|---|---|---|---|
| 1 | `deploy-staging.yml` (22K) — knapp über Limit, aber `workflow_run` | ⚠️ Akzeptiert (kein Limit bei workflow_run) | P3 |
| 2 | `deploy-staging.yml` für Konsistenz auch refaktorisieren | ⬜ Offen | P3 |
| 3 | CI/CD Pre-Deploy-Check für File-Größe einbauen | ⬜ Offen | P2 |

---

## 9. CI/CD Flow (neu)

```
┌─────────────────────────────────────────────────────┐
│                PRODUCTION DEPLOY FLOW                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  GitHub UI / API → workflow_dispatch                 │
│    ↓                                                 │
│  pre-flight (confirm=yes)                           │
│    ↓                                                 │
│  pre-deploy-backup (Velero Backup)                  │
│    ↓                                                 │
│  deploy:                                             │
│    ├── SCP infrastructure/ → /root/production-manifests/ │
│    ├── SCP scripts/deploy-prod/ → /root/deploy-scripts/  │
│    └── SSH: bash /root/deploy-scripts/deploy-all.sh  │
│         ├── 01-pull-images.sh                       │
│         ├── 02-apply-manifests.sh                   │
│         ├── 03-deploy-livekit.sh                    │
│         ├── 04-velero-scope-check.sh                │
│         ├── 05-install-infra.sh                     │
│         ├── 06-deploy-system.sh                     │
│         ├── 07-deploy-apps.sh                       │
│         ├── 08-setup-n8n.sh                         │
│         └── 09-smoke-tests.sh                       │
│                                                      │
└─────────────────────────────────────────────────────┘
```
