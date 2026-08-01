# AGENTS DEPLOY FLOW — Staging & Production

## GOLDEN RULE

**Wenn du Code oder DB-Änderungen in Staging/Production machst: NIEMALS manuell deployen. Immer den CI/CD Flow nutzen.**

## Quick Reference (3-Zeilen-Summary)

```
git push to main → GitHub Actions baut Image → k3s pulled automatisch → alembic-migrate wendet Migration an
```

**Du musst NICHTS manuell deployen. Nur pushen. CI/CD macht den Rest.**

---

## Korrekter Ablauf (jede Änderung)

### Schritt 1: Änderungen vorbereiten

```
1a. Code-Änderungen in backend/ oder frontend/
1b. Falls DB-Schema-Änderung: alembic revision --autogenerate
1c. Tests lokal laufen lassen (pytest / npm test)
1d. Code-Reviewer spawnen
```

### Schritt 2: Git Commit + Push

```
2a. git add .
2b. git commit (konventioneller Commit Message)
2c. git push origin main
```

### Schritt 3: CI/CD Pipeline (AUTOMatisch!)

```
Push to main triggert e2e-tests.yml:

Job 1: build-and-test-dev
  ├─ Docker Image bauen (multi-arch: amd64 + arm64)
  ├─ DEV E2E Tests (docker-compose.e2e.yml)
  └─ Push zu Docker Hub (SHA-Tag + :latest)

Job 2: deploy-staging-and-test (nur main branch)
  ├─ kubectl set image deployment/backend
  │   backend=IMAGE:SHA
  │   alembic-migrate=IMAGE:SHA     ← WICHTIG!
  ├─ kubectl set image deployment/frontend
  ├─ kubectl set image deployment/celery-worker-staging
  ├─ kubectl set image deployment/celery-worker-pro-staging
  ├─ kubectl set image deployment/celery-beat-staging
  ├─ alembic-migrate Init-Container → alembic upgrade head
  └─ Staging E2E Tests (≥95% Pass-Rate Gate)

Job 3: deploy-production (nur wenn Job 2 ≥95%)
  ├─ Gleicher Mechanismus wie Job 2
  ├─ Namespace: meeting-automation (NICHT staging!)
  └─ Production Smoke Tests
```

---

## Was NICHT erlaubt ist

| ❌ VERBOTEN | ✅ RICHTIG |
|---|---|
| `docker build` lokal für Staging/Production | CI/CD baut automatisch |
| `k3s ctr images import` | k3s pulled von Docker Hub |
| `kubectl set image` manuell | CI/CD macht das |
| `kubectl rollout restart` manuell | Rolling Update via `set image` |
| `alembic upgrade head` manuell | alembic-migrate Init-Container |
| `docker save | k3s ctr import -` (Pipe) | Funktioniert NICHT (C10) |

---

## Ausnahme: Lokales Testing (NICHT Deploy!)

Nur für lokales Testen vor dem Push:

```
docker compose up -d          ← Nur für lokale Entwicklung
pytest tests/                 ← Nur für lokale Tests
npm run dev                   ← Nur für lokales Frontend
```

**Aber NIEMALS als Staging/Production Deploy nutzen!**

---

## Wenn CI/CD Pipeline fehlschlägt

1. GitHub Actions Logs prüfen (`gh run view <ID> --log`)
2. Fehler analysieren
3. Code fixen
4. Erneut pushen (CI/CD läuft automatisch)
5. **NUR als letztes Mittel**: Manueller Deploy auf Staging (BAUPLAN Pattern)

---

## HARTE LESSONS (aus BAUPLAN.md + STAGING_MODIFIKATION.md)

| # | Regel |
|---|-------|
| **C7** | `SKIP_SENTINEL=true` DARF NIEMALS für Prod/Staging-Builds genutzt werden — entfernt llama-cpp-python + Qwen GGUF → PRO/ENT Worker verlieren Sentinel LLM. CI/CD nutzt Variante B (InitContainer + PVC). |
| **C10** | `docker save | k3s ctr images import -` (Pipe) funktioniert NICHT → `total: 0.0 B`. Immer: `docker save -o file.tar` → `k3s ctr images import file.tar`. |
| **K23** | **Jeder neue Worker-Tier MUSS in ALLE Server-NetworkPolicies**: rabbitmq-policy, redis-policy, postgres-policy, minio-policy, cnpg-policy. Sonst Connection-refused → Crash-Loop. |
| **N1** | `imagePullPolicy: Always` + lokale Images = ImagePullBackOff. Bei lokalem Import MUSS `IfNotPresent` gesetzt sein. CI/CD nutzt Docker Hub Pull (funktioniert mit `Always`). |
| **Docker Hub Pull Secret** | CI/CD erstellt `dockerhub-pull-secret` + patched alle Deployments. Neue manuelle Deployments brauchen diesen Secret manuell! |
| **Variante B** | Sentinel LLM wird NICHT im Docker Image mitgeliefert (SKIP_SENTINEL=true). Stattdessen: InitContainer `sentinel-download` lädt von MinIO → PVC `sentinel-models-claim`. |

---

## Referenz-Dateien

| Datei | Zweck |
|---|---|
| `.github/workflows/e2e-tests.yml` | CI/CD Pipeline (Build + Deploy) |
| `.github/workflows/docker-build.yml` | Multi-Arch Docker Build |
| `backend/Dockerfile` | Docker Image Definition |
| `infrastructure/kubernetes/staging/backend-deployment.yaml` | Staging Deployment |
| `BAUPLAN.md` | Vollständiger Deploy-Ablauf |
| `docs/STAGING_MODIFIKATION.md` | Bekannte Deploy-Probleme + Fixes |
| `docs/STAGING_RECOVERY_PLAN.md` | Recovery-Verfahren |
| `.loop.md` | Phase-Tracking + HARTE LESSONS |
| `AGENTS.md` | Quick-Start für Agenten |
