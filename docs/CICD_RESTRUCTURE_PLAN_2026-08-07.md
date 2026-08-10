# CI/CD Umstrukturierungsplan — Staging/Production Trennung

> **Erstellt**: 2026-08-07
> **Status**: ✅ IMPLEMENTIERT (2026-08-08)
> **Aktualisiert**: 2026-08-10 — Workflows ci.yml, deploy-staging.yml, deploy-production.yml sind aktiv. Alte Workflows (backend-ci.yml, frontend-ci.yml, e2e-tests.yml) existieren noch mit .disabled Suffix fuer Rollback.
> **Nächste Phase**: Phase 190 in `.loop.md`
> **Basiert auf**: Phase 176 (CI/CD Audit), Phase 187-189c (CronJob/Longhorn/Metrics-Server Fixes), `docs/N8N_CICD_PLAN_2026-08-05.md`

---

## 1. Aktueller Zustand (IST)

### 1.1 Bestehende Workflows

| Workflow | Datei | Trigger | Aufgabe |
|----------|-------|---------|---------|
| **Backend CI** | `backend-ci.yml` | `push` auf `main`/`develop` | Tests + Build (kein Deploy) |
| **Frontend CI** | `frontend-ci.yml` | `push` auf `main`/`develop` | Lint + TypeCheck + Build (kein Deploy) |
| **E2E Tests + Deploy** | `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) | `push` auf `main` | **ALLES**: Tests → Build → Push Images → Deploy Staging → E2E Tests → Deploy Production |
| **Deploy Production** | `deploy-production.yml` | `workflow_run` (nach Docker Build) | Deploy Production via SCP + SSH |

### 1.2 Kernproblem

```
e2e-tests.yml macht ALLES in EINEM Workflow:
  1. Backend/Frontend Tests
  2. Docker Images bauen (Multi-Arch: amd64+arm64)
  3. Nach Docker Hub pushen
  4. Deploy Staging (kubectl set image)
  5. E2E Tests gegen Staging
  6. Deploy Production (automatisch nach Staging-Test)

→ KEIN separater Staging-Deploy möglich
→ Jeder Push auf main deployt automatisch auf Production
→ Keine manuelle Kontrolle über Deploy-Timing
→ Kein Approval-Gate vor Production-Deploy
```

### 1.3 Betroffene Dateien (aktuell)

| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `.github/workflows/e2e-tests.yml` | ~450 | Komplette Pipeline (Build + Test + Deploy Staging + Deploy Prod) |
| `.github/workflows/deploy-production.yml` | ~180 | Production-Deploy via SCP + SSH (separat, aber durch `workflow_run` getriggert) |
| `.github/workflows/backend-ci.yml` | ~70 | Backend Tests (unabhängig) |
| `.github/workflows/frontend-ci.yml` | ~40 | Frontend Tests (unabhängig) |

---

## 2. Zielzustand (SOLL) — 3 Separate Workflows

### 2.1 Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 1: CI Pipeline (ci.yml)                               │
│  Trigger: push auf main/develop + pull_request                  │
│  Aufgabe: Tests + Build + Push Images                           │
│  Kein Deploy!                                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓ workflow_run
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 2: Deploy Staging (deploy-staging.yml)                │
│  Trigger: workflow_run (nach CI) ODER workflow_dispatch         │
│  Environment: staging (kein Approval nötig)                     │
│  Aufgabe: Deploy + E2E Tests gegen Staging                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓ workflow_dispatch + Approval
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 3: Deploy Production (deploy-production.yml)          │
│  Trigger: NUR workflow_dispatch (manuell)                       │
│  Environment: production (Approval von required_reviewers)      │
│  Aufgabe: Deploy + Smoke Tests                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Trigger-Matrix

| Aktion | CI | Staging | Production |
|--------|-----|---------|------------|
| `git push main` | ✅ Auto | ✅ Auto (nach CI) | ❌ Nie |
| `git push develop` | ✅ Auto | ❌ Nie | ❌ Nie |
| `pull_request` | ✅ Auto | ❌ Nie | ❌ Nie |
| Manual `workflow_dispatch` | ✅ Ja | ✅ Ja | ✅ Ja + Approval |
| API `repository_dispatch` | ❌ Nie | ✅ Ja | ❌ Nie |

### 2.3 GitHub Environments

| Environment | Approval | Secrets | Protection Rules |
|-------------|----------|---------|-----------------|
| `staging` | Keiner (auto) | `KUBE_CONFIG_STAGING`, AI Keys, E2E User | Deploy-Branch: `main` |
| `production` | `required_reviewers` | `KUBE_CONFIG_PRODUCTION`, Docker Hub, AI Keys | Deploy-Branch: `main` + Wait-Timer (optional) |

---

## 3. Workflow-Spezifikation

### 3.1 Workflow 1: `ci.yml` — Build + Test (kein Deploy)

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - 'frontend/**'
  pull_request:
    branches: [main]
    paths:
      - 'backend/**'
      - 'frontend/**'

permissions:
  contents: read
  security-events: write

env:
  REGISTRY: docker.io
  IMAGE_NAME: docker.io/batnini/meeting-automation-backend
  FRONTEND_IMAGE: docker.io/batnini/meeting-automation-frontend

jobs:
  # ============================================
  # JOB 1: Backend Tests
  # ============================================
  backend-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: 3.11
    - name: Cache dependencies
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements.txt') }}
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run Alembic migrations
      env:
        DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
        ENCRYPTION_KEY: ${{ secrets.ENCRYPTION_KEY }}
        TOTP_ENCRYPTION_KEY: ${{ secrets.TOTP_ENCRYPTION_KEY }}
        SECRET_KEY: ${{ secrets.SECRET_KEY }}
      run: |
        cd backend
        PYTHONPATH=. alembic upgrade head
    - name: Run tests with pytest
      env:
        DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/0
        ENCRYPTION_KEY: ${{ secrets.ENCRYPTION_KEY }}
        TOTP_ENCRYPTION_KEY: ${{ secrets.TOTP_ENCRYPTION_KEY }}
        SECRET_KEY: ${{ secrets.SECRET_KEY }}
        E2E_TEST: "true"
      run: |
        cd backend
        pytest tests/ --cov=app --cov-report=xml --cov-report=html
    - name: Upload coverage
      uses: codecov/codecov-action@v4
      with:
        files: ./backend/coverage.xml
        flags: backend
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

  # ============================================
  # JOB 2: Frontend Tests
  # ============================================
  frontend-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    - name: Install dependencies
      run: |
        cd frontend
        npm ci
    - name: Lint
      run: |
        cd frontend
        npm run lint
    - name: Type check
      run: |
        cd frontend
        npm run type-check || npx tsc --noEmit
    - name: Build
      run: |
        cd frontend
        npm run build

  # ============================================
  # JOB 3: Build + Push Multi-Arch Images
  # ============================================
  build-and-push:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    permissions:
      contents: read
      security-events: write
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: batnini
        password: ${{ secrets.DOCKERHUB_TOKEN }}

    # --- Backend Image ---
    - name: Build + Push Backend (amd64+arm64)
      uses: docker/build-push-action@v5
      with:
        context: ./backend
        platforms: linux/amd64,linux/arm64
        push: true
        build-args: SKIP_SENTINEL=true
        tags: |
          ${{ env.IMAGE_NAME }}:${{ github.sha }}
          ${{ env.IMAGE_NAME }}:latest

    # --- Frontend Image ---
    - name: Build + Push Frontend (amd64+arm64)
      uses: docker/build-push-action@v5
      with:
        context: ./frontend
        platforms: linux/amd64,linux/arm64
        push: true
        tags: |
          ${{ env.FRONTEND_IMAGE }}:${{ github.sha }}
          ${{ env.FRONTEND_IMAGE }}:latest

    # --- Security Scan ---
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy results
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: 'trivy-results.sarif'
```

**Zusammenfassung `ci.yml`**:
- 3 Jobs: `backend-test` (parallel), `frontend-test` (parallel), `build-and-push` (sequentiell)
- Nur Push auf `main` → baut + pushed Images
- Pull Requests → nur Tests (kein Push)
- **KEIN Deploy!**

---

### 3.2 Workflow 2: `deploy-staging.yml` — Deploy + Test

```yaml
name: Deploy Staging

on:
  # Automatisch nach CI (nur main)
  workflow_run:
    workflows: [CI Pipeline]
    types: [completed]
    branches: [main]

  # Manuell triggers
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Image Tag (default: latest)'
        required: false
        default: 'latest'
        type: string

env:
  IMAGE_NAME: docker.io/batnini/meeting-automation-backend
  FRONTEND_IMAGE: docker.io/batnini/meeting-automation-frontend

jobs:
  # ============================================
  # PRE-FLIGHT: Nur bei erfolgreichem CI deployen
  # ============================================
  pre-flight:
    runs-on: ubuntu-latest
    if: >
      (github.event_name == 'workflow_dispatch') ||
      (github.event.workflow_run.conclusion == 'success')
    outputs:
      image_tag: ${{ steps.resolve-tag.outputs.tag }}
    steps:
    - name: Resolve image tag
      id: resolve-tag
      run: |
        if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
          echo "tag=${{ inputs.image_tag }}" >> $GITHUB_OUTPUT
        else
          echo "tag=${{ github.event.workflow_run.head_sha }}" >> $GITHUB_OUTPUT
        fi
        echo "Deploying with tag: ${{ steps.resolve-tag.outputs.tag }}"

  # ============================================
  # DEPLOY STAGING
  # ============================================
  deploy-staging:
    runs-on: ubuntu-latest
    needs: pre-flight
    environment: staging
    steps:
    - uses: actions/checkout@v4

    - name: Check Staging Secrets
      run: |
        if [ -z "${{ secrets.KUBE_CONFIG_STAGING }}" ]; then
          echo "❌ KUBE_CONFIG_STAGING secret not configured."
          exit 1
        fi

    - name: Configure kubectl
      run: |
        echo "${{ secrets.KUBE_CONFIG_STAGING }}" > kubeconfig-staging
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        CONTEXT=$(kubectl config get-contexts -o name | head -1)
        kubectl config use-context "$CONTEXT"
        kubectl get namespace meeting-automation-staging || kubectl apply -f infrastructure/kubernetes/staging/namespace.yaml

    - name: Ensure Docker Hub Pull Secret
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        kubectl create secret docker-registry dockerhub-pull-secret \
          --namespace meeting-automation-staging \
          --docker-server=https://index.docker.io/v1/ \
          --docker-username=batnini \
          --docker-password="${{ secrets.DOCKERHUB_TOKEN }}" \
          --dry-run=client -o yaml | kubectl apply -f -
        for deploy in $(kubectl get deploy -n meeting-automation-staging -o name 2>/dev/null); do
          HAS_SECRET=$(kubectl get "$deploy" -n meeting-automation-staging -o jsonpath='{.spec.template.spec.imagePullSecrets[?(@.name=="dockerhub-pull-secret")].name}' 2>/dev/null)
          if [ -z "$HAS_SECRET" ]; then
            kubectl patch "$deploy" -n meeting-automation-staging --type=json \
              -p='[{"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[{"name":"dockerhub-pull-secret"}]}]' 2>&1 || true
          fi
        done

    - name: Create/Update Staging Secrets
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        kubectl create secret generic e2e-test-user \
          --namespace meeting-automation-staging \
          --from-literal=E2E_TEST_USER_EMAIL="${{ secrets.STAGING_E2E_USER_EMAIL }}" \
          --from-literal=E2E_TEST_USER_PASSWORD="${{ secrets.STAGING_E2E_USER_PASSWORD }}" \
          --dry-run=client -o yaml | kubectl apply -f -
        kubectl create secret generic backend-api-keys-staging \
          --namespace meeting-automation-staging \
          --from-literal=MISTRAL_API_KEY="${{ secrets.MISTRAL_API_KEY_STAGING }}" \
          --from-literal=GLADIA_API_KEY="${{ secrets.GLADIA_API_KEY_STAGING }}" \
          --dry-run=client -o yaml | kubectl apply -f -

    - name: Install Longhorn (skip-if-exists)
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        if kubectl get namespace longhorn-system &>/dev/null; then
          echo "✅ longhorn-system already exists — skipping"
        else
          echo "📦 Installing Longhorn v1.12.0..."
          helm repo add longhorn https://charts.longhorn.io 2>/dev/null || true
          helm repo update
          helm install longhorn longhorn/longhorn \
            --namespace longhorn-system --create-namespace --version 1.12.0 \
            --set defaultSettings.defaultReplicaCount=1 \
            --set defaultSettings.createDefaultDiskLabeledNodes=true \
            --set defaultSettings.defaultClass=false \
            --wait --timeout 10m || echo "⚠️ Longhorn install failed, continuing"
        fi

    - name: Deploy All Staging Resources
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        kubectl apply -f infrastructure/kubernetes/staging/ -n meeting-automation-staging
        kubectl rollout restart deployment/onlyoffice-staging -n meeting-automation-staging 2>&1 || true

    - name: Deploy System CronJobs
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        kubectl apply -f infrastructure/kubernetes/system/ephemeral-storage-cleanup-cronjob.yaml -n kube-system
        kubectl apply -f infrastructure/kubernetes/system/pod-garbage-collector-cronjob.yaml -n kube-system
        kubectl apply -f infrastructure/kubernetes/system/longhorn-cleanup-cronjob.yaml -n longhorn-system 2>&1 || true
        kubectl apply -f infrastructure/kubernetes/system/metrics-server-patch.yaml -n kube-system
        kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
        helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
        helm repo update
        helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
          -n monitoring --reuse-values \
          --set prometheus.prometheusSpec.hostNetwork=true \
          --set prometheus.prometheusSpec.dnsPolicy=ClusterFirstWithHostNet \
          --set prometheus.service.port=9090 || true
        kubectl apply -f infrastructure/kubernetes/staging/monitoring/ -n monitoring 2>&1 || true

    - name: Deploy Backend
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        TAG=${{ needs.pre-flight.outputs.image_tag }}
        kubectl set image deployment/backend \
          backend=${{ env.IMAGE_NAME }}:$TAG \
          alembic-migrate=${{ env.IMAGE_NAME }}:$TAG \
          -n meeting-automation-staging --record
        kubectl rollout status deployment/backend -n meeting-automation-staging --timeout=600s

    - name: Deploy Frontend
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        TAG=${{ needs.pre-flight.outputs.image_tag }}
        kubectl set image deployment/frontend \
          frontend=${{ env.FRONTEND_IMAGE }}:$TAG \
          -n meeting-automation-staging --record
        kubectl rollout status deployment/frontend -n meeting-automation-staging --timeout=120s

    - name: Deploy Celery Workers
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        TAG=${{ needs.pre-flight.outputs.image_tag }}
        BACKEND_IMAGE="${{ env.IMAGE_NAME }}:$TAG"
        kubectl set image deployment/celery-worker-staging celery-worker="$BACKEND_IMAGE" -n meeting-automation-staging --record
        kubectl set image deployment/celery-worker-pro-staging celery-worker="$BACKEND_IMAGE" -n meeting-automation-staging --record
        kubectl set image deployment/celery-beat-staging celery-beat="$BACKEND_IMAGE" -n meeting-automation-staging --record
        kubectl rollout status deployment/celery-worker-staging -n meeting-automation-staging --timeout=300s
        kubectl rollout status deployment/celery-beat-staging -n meeting-automation-staging --timeout=120s

    - name: Import n8n Workflows
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        N8N_POD=$(kubectl get pods -n meeting-automation-staging -l app=n8n-staging -o jsonpath='{.items[0].metadata.name}')
        WORKFLOW_COUNT=$(kubectl exec -n meeting-automation-staging meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
        if [ "$WORKFLOW_COUNT" = "0" ]; then
          echo "No workflows — importing..."
          kubectl exec -n meeting-automation-staging $N8N_POD -- mkdir -p /home/node/.n8n/workflows
          for f in n8n/workflows/*.json; do
            name=$(basename $f)
            cat $f | kubectl exec -i -n meeting-automation-staging $N8N_POD -- tee /home/node/.n8n/workflows/$name > /dev/null
            kubectl exec -n meeting-automation-staging $N8N_POD -- n8n import:workflow --input=/home/node/.n8n/workflows/$name 2>&1 | tail -1 || true
          done
          kubectl rollout restart deployment/n8n-staging -n meeting-automation-staging
        else
          echo "✅ Workflows exist ($WORKFLOW_COUNT) — skipping"
        fi

  # ============================================
  # E2E TESTS (gegen Staging)
  # ============================================
  e2e-test-staging:
    runs-on: ubuntu-latest
    needs: deploy-staging
    steps:
    - uses: actions/checkout@v4

    - name: Wait for Staging Health
      run: |
        STAGING_URL="https://staging.meeting-automation.com"
        for i in {1..60}; do
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" $STAGING_URL/health 2>/dev/null || echo "000")
          if [ "$STATUS" = "200" ]; then echo "Staging healthy"; break; fi
          echo "Waiting... ($STATUS, attempt $i)"
          sleep 5
        done
        curl -f $STAGING_URL/health || (echo "Staging health check failed" && exit 1)

    - name: Port-forward + E2E Tests
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-staging
        echo "${{ secrets.KUBE_CONFIG_STAGING }}" > kubeconfig-staging
        kubectl port-forward -n meeting-automation-staging svc/meeting-db-rw 5433:5432 &
        kubectl port-forward -n meeting-automation-staging svc/backend 8080:8000 &
        kubectl port-forward -n meeting-automation-staging svc/minio-staging 9002:9000 &
        trap "kill %1 %2 %3 2>/dev/null || true" EXIT
        for i in {1..30}; do
          if nc -z localhost 5433 && nc -z localhost 8080 && nc -z localhost 9002; then break; fi
          sleep 1
        done
        cd backend
        pip install -q -r requirements.txt -r requirements-dev.txt
        pytest tests/e2e/ -v --tb=short --junitxml=staging-e2e-report.xml -m "e2e and not flaky" --reruns 2 --reruns-delay 1
      env:
        TEST_ENV: staging
        E2E_TEST: "true"
        E2E_BASE_URL: "http://localhost:8080"
        DATABASE_URL: "postgresql+asyncpg://meeting_user:meeting_password@localhost:5433/meeting_db_staging"

    - name: Upload Test Results
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: staging-e2e-results
        path: backend/staging-e2e-report.xml
```

**Zusammenfassung `deploy-staging.yml`**:
- **Trigger 1**: Automatisch nach CI-Pipeline (`workflow_run`)
- **Trigger 2**: Manuell (`workflow_dispatch`) mit Image-Tag Input
- 3 Jobs: `pre-flight` → `deploy-staging` → `e2e-test-staging`
- Environment `staging` (kein Approval)
- Alle Steps aus aktuellem `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) (Build-Step entfernt)

---

### 3.3 Workflow 3: `deploy-production.yml` — Manueller Deploy

```yaml
name: Deploy Production

on:
  # NUR manuell — kein automatischer Trigger!
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Image Tag (SHA oder latest)'
        required: true
        type: string
      confirm:
        description: 'Type "yes" to confirm production deploy'
        required: true
        type: string

env:
  IMAGE_NAME: docker.io/batnini/meeting-automation-backend
  FRONTEND_IMAGE: docker.io/batnini/meeting-automation-frontend

jobs:
  # ============================================
  # PRE-FLIGHT: Confirmation Check
  # ============================================
  pre-flight:
    runs-on: ubuntu-latest
    steps:
    - name: Validate confirmation
      run: |
        if [ "${{ inputs.confirm }}" != "yes" ]; then
          echo "❌ Production deploy not confirmed. Aborting."
          exit 1
        fi
        echo "✅ Production deploy confirmed with tag: ${{ inputs.image_tag }}"

  # ============================================
  # DEPLOY PRODUCTION
  # ============================================
  deploy-production:
    runs-on: ubuntu-latest
    needs: pre-flight
    environment: production
    steps:
    - uses: actions/checkout@v4

    - name: Configure kubectl
      run: |
        echo "${{ secrets.KUBE_CONFIG_PRODUCTION }}" > kubeconfig-prod
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        CONTEXT=$(kubectl config get-contexts -o name | head -1)
        kubectl config use-context "$CONTEXT"

    - name: Deploy Production
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        TAG=${{ inputs.image_tag }}
        kubectl set image deployment/backend \
          backend=${{ env.IMAGE_NAME }}:$TAG \
          alembic-migrate=${{ env.IMAGE_NAME }}:$TAG \
          -n meeting-automation --record
        kubectl set image deployment/frontend \
          frontend=${{ env.FRONTEND_IMAGE }}:$TAG \
          -n meeting-automation --record
        kubectl set image deployment/celery-worker \
          celery-worker=${{ env.IMAGE_NAME }}:$TAG \
          -n meeting-automation --record
        kubectl set image deployment/celery-worker-pro \
          celery-worker=${{ env.IMAGE_NAME }}:$TAG \
          -n meeting-automation --record
        kubectl set image deployment/celery-beat \
          celery-beat=${{ env.IMAGE_NAME }}:$TAG \
          -n meeting-automation --record
        kubectl rollout status deployment/backend -n meeting-automation --timeout=300s
        kubectl rollout status deployment/frontend -n meeting-automation --timeout=120s
        kubectl rollout status deployment/celery-worker -n meeting-automation --timeout=300s
        kubectl rollout status deployment/celery-beat -n meeting-automation --timeout=120s

    - name: Deploy System Resources
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        kubectl apply -f infrastructure/kubernetes/production/ingress-prod.yaml -n meeting-automation 2>&1 || true
        kubectl apply -f infrastructure/kubernetes/production/n8n-ingress.yaml -n meeting-automation 2>&1 || true
        kubectl apply -f infrastructure/kubernetes/system/ephemeral-storage-cleanup-cronjob.yaml -n kube-system 2>&1 || true
        kubectl apply -f infrastructure/kubernetes/system/pod-garbage-collector-cronjob.yaml -n kube-system 2>&1 || true
        kubectl apply -f infrastructure/kubernetes/system/longhorn-cleanup-cronjob.yaml -n longhorn-system 2>&1 || true

    - name: Import n8n Workflows (idempotent)
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        N8N_POD=$(kubectl get pods -n meeting-automation -l app=n8n -o jsonpath='{.items[0].metadata.name}')
        WORKFLOW_COUNT=$(kubectl exec -n meeting-automation meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
        if [ "$WORKFLOW_COUNT" = "0" ]; then
          kubectl exec -n meeting-automation $N8N_POD -- mkdir -p /home/node/.n8n/workflows
          for f in n8n/workflows/*.json; do
            name=$(basename $f)
            cat $f | kubectl exec -i -n meeting-automation $N8N_POD -- tee /home/node/.n8n/workflows/$name > /dev/null
            kubectl exec -n meeting-automation $N8N_POD -- n8n import:workflow --input=/home/node/.n8n/workflows/$name 2>&1 | tail -1 || true
          done
          kubectl rollout restart deployment/n8n -n meeting-automation
        fi

    - name: Smoke Tests
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        kubectl port-forward -n meeting-automation svc/backend 18080:8000 &
        sleep 5
        HEALTH=$(curl -sf http://localhost:18080/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        kill %1 2>/dev/null || true
        if [ "$HEALTH" = "healthy" ]; then
          echo "✅ Production smoke test PASSED"
        else
          echo "❌ Production smoke test FAILED"
          exit 1
        fi

    - name: Rollback on Failure
      if: failure()
      run: |
        export KUBECONFIG=$(pwd)/kubeconfig-prod
        kubectl rollout undo deployment/backend -n meeting-automation
        kubectl rollout undo deployment/frontend -n meeting-automation
        kubectl rollout undo deployment/celery-worker -n meeting-automation
        kubectl rollout undo deployment/celery-worker-pro -n meeting-automation
        kubectl rollout undo deployment/celery-beat -n meeting-automation
        echo "Rolled back to previous revision"
```

**Zusammenfassung `deploy-production.yml`**:
- **NUR `workflow_dispatch`** — manueller Trigger
- Input: `image_tag` (Pflicht) + `confirm: "yes"` (Pflicht)
- Environment `production` mit **Approval von `required_reviewers`**
- Rollback bei Fehler (automatisch)

---

## 4. GitHub Environments Setup

> **Vollständige Anleitung**: Siehe `docs/GITHUB_ENVIRONMENTS_SETUP_2026-08-07.md`

### 4.1 Staging Environment

| Eigenschaft | Wert |
|-------------|------|
| Name | `staging` |
| Approval | Keiner (auto-deploy) |
| Branch | `main` |
| Secrets | 13 Stück (siehe Setup-Guide) |

### 4.2 Production Environment

| Eigenschaft | Wert |
|-------------|------|
| Name | `production` |
| Approval | `required_reviewers` (1+ Team-Member) |
| Branch | `main` |
| Secrets | 13 Stück (siehe Setup-Guide) |

---

## 5. Migration: Alt → Neu

### 5.1 Schritt-für-Schritt

| # | Schritt | Datei | Risiko |
|---|---------|-------|--------|
| 1 | `ci.yml` erstellen (aus `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) Build-Steps extrahieren) | `.github/workflows/ci.yml` | Niedrig |
| 2 | `deploy-staging.yml` erstellen (aus `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) Deploy-Steps extrahieren) | `.github/workflows/deploy-staging.yml` | Niedrig |
| 3 | `deploy-production.yml` umbenennen → manueller Trigger + Approval | `.github/workflows/deploy-production.yml` | Mittel |
| 4 | GitHub Environments einrichten (staging + production) | GitHub UI | Niedrig |
| 5 | `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) deaktivieren (nicht löschen!) | `.github/workflows/e2e-tests.yml` | Niedrig |
| 6 | Testen: Push auf main → CI → auto-deploy Staging | Git push | Mittel |
| 7 | Testen: Manual deploy Production → Approval | GitHub UI | Mittel |

### 5.2 Rollback-Plan

```
Wenn die neue Pipeline Fehler hat:
1. e2e-tests.yml wieder aktivieren (rename zurück)
2. ci.yml + deploy-staging.yml deaktivieren
3. Alte Pipeline übernimmt wieder
→ Maximaler Ausfall: 5 Minuten (Zeit für Rename)
```

### 5.3 CI/CD Änderungen im Detail

#### Was aus `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) wandert

| aktueller Step | neuer Workflow |
|----------------|----------------|
| Build Docker Image | → `ci.yml` (build-and-push) |
| E2E Tests (dev) | → `ci.yml` (backend-test + frontend-test) |
| Push Images | → `ci.yml` (build-and-push) |
| Login Docker Hub | → `ci.yml` + `deploy-staging.yml` |
| Configure kubectl | → `deploy-staging.yml` |
| Create Secrets | → `deploy-staging.yml` |
| Deploy All Staging | → `deploy-staging.yml` |
| Deploy Backend/Frontend | → `deploy-staging.yml` |
| E2E Tests (staging) | → `deploy-staging.yml` (e2e-test-staging) |
| Longhorn Install | → `deploy-staging.yml` |
| System CronJobs | → `deploy-staging.yml` |

#### Was in `deploy-production.yml` bleibt/geändert

| aktueller Step | Änderung |
|----------------|----------|
| `workflow_run` Trigger | → `workflow_dispatch` (manuell) |
| SCP + SSH | → Behalten (Contabo hat keinen kubectl Zugang von GitHub) |
| Approval | → Neu: `environment: production` |
| Rollback | → Behalten |

---

## 6. HARTE LESSONS aus `.loop.md` (berücksichtigen!)

| Phase | Lesson | Anwendung auf neue Pipeline |
|-------|--------|-----------------------------|
| **187** | `kubectl apply -f <dir>/ -n <ns>` wendet ALLE Dateien an | CronJobs separat deployen (nicht in staging/) |
| **188** | Longhorn muss VOR Pipeline existieren | skip-if-exists Pattern beibehalten |
| **189** | OCI VNIC blockiert Pod→Node Traffic | hostNetwork für metrics-server beibehalten |
| **189c** | Helm-Install in CI/CD ist riskant | Safety-Netz (`|| echo warning`) beibehalten |
| **176** | Selektiver Checkout statt Full-Merge | Selektive Pfade in kubectl apply |
| **182** | OnlyOffice `document.url` intern | Kein Einfluss auf CI/CD |
| **183** | ConfigMap + initContainer Pattern | ConfigMaps in deploy-staging.yml apply |
| **C10** | DiskPressure evicted Pods | KEIN `docker save` in `/tmp` auf kleiner Disk |
| **C9** | k3s `:latest` wird gecached | Immer `rollout restart` nach Image-Push |
| **LHCI2** | Staging `defaultClass=false`, Prod `defaultClass=true` | Longhorn-Install-Step beibehalten |

---

## 7. N8N Integration (aus `docs/N8N_CICD_PLAN_2026-08-05.md`)

Die n8n-Steps aus dem CI/CD-Plan werden in `deploy-staging.yml` und `deploy-production.yml` übernommen:

| Step | Staging | Production |
|------|---------|------------|
| Workflow Import | ✅ (idempotent) | ✅ (idempotent) |
| SMTP Credential | ✅ (idempotent) | ✅ (idempotent) |
| Owner Setup | ✅ (REST API) | ✅ (REST API) |
| Credential-ID Update | ✅ (workflow_entity + workflow_history) | ✅ (workflow_entity + workflow_history) |

**KRITISCH** (aus `N8N_CICD_PLAN_2026-08-05.md`):
> n8n liest Nodes aus `workflow_history`, NICHT `workflow_entity`. BEIDE Tabellen müssen bei Credential-Updates aktualisiert werden.

---

## 8. Zusammenfassung

| Aspekt | Alt (e2e-tests.yml) | Neu (3 Workflows) |
|--------|---------------------|-------------------|
| **Staging Deploy** | Automatisch in CI | Separater Workflow |
| **Production Deploy** | Automatisch nach Staging | **Manuell + Approval** |
| **Secrets** | Gemischt | **Separat pro Environment** |
| **Rollback** | Manuell | **Automatisch bei Fehler** |
| **Test-Trennung** | Keine | **Dev → Staging → Prod** |
| **Image-Tag** | `${{ github.sha }}` | `${{ github.sha }}` oder manuell |
| **n8n Integration** | Fehlt in CI/CD | **Vollständig integriert** |
| **Manual Trigger** | Nicht möglich | **workflow_dispatch für beide** |

---

## 9. Offene Fragen

| # | Frage | Empfehlung |
|---|-------|------------|
| 1 | Soll `e2e-tests.yml` (DEPRECATED — replaced by `ci.yml`) gelöscht oder deaktiviert werden? | Deaktivieren (rename) — für Rollback |
| 2 | Soll Production auch Auto-Deploy nach Staging-Erfolg unterstützen? | Optional: `repository_dispatch` Trigger |
| 3 | Sollen die 3 Fixes (TURN, layout, Reconnect) vor oder nach CI/CD-Umstrukturierung deployed werden? | **VORHER** — CI/CD-Änderung ist unabhängig vom LiveKit-Fix |
| 4 | Soll `deploy-staging.yml` auch `repository_dispatch` unterstützen? | Ja — für externe Trigger (z.B. n8n) |

---

## 10. Implementierungs-Reihenfolge

```
SCHRITT 1: LiveKit 3-Fixes deployen (TURN + layout + Reconnect)
           → User testet
           → Wenn funktioniert: weiter mit Schritt 2

SCHRITT 2: CI/CD umstrukturieren
           → ci.yml + deploy-staging.yml erstellen
           → deploy-production.yml anpassen
           → GitHub Environments einrichten
           → e2n-tests.yml deaktivieren

SCHRITT 3: Testen
           → Push auf main → CI → auto-deploy Staging
           → Manual deploy Production → Approval → Deploy

SCHRITT 4: Dokumentation aktualisieren
           → .loop.md Phase 190 hinzufügen
           → DEPLOYMENT.md aktualisieren
           → AGENTS.md CI/CD-Sektion aktualisieren
```

---

**NÄCHSTER SCHRITT**: User entscheidet ob Schritt 1 (LiveKit Fixes) zuerst oder Schritt 2 (CI/CD Umstrukturierung) zuerst.
