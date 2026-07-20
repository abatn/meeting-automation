# SKILL: Staging Kubernetes Operations

Rapid diagnosis and management of the staging k3s cluster. Covers pod lookup, exec, DB queries, log inspection, and service restarts — all the operations repeatedly needed when debugging the staging environment.

**Description:** Provides standardized commands for interacting with the meeting-automation-staging namespace on the k3s cluster. Eliminates the need to reconstruct kubectl commands from scratch each time.

## When to Use

- User asks to "check staging logs", "check die logs der staging", "check die container"
- Debugging LiveKit pipeline errors in staging
- Running DB queries against the staging database
- Checking pod status, health, or restart history
- Inspecting n8n, Celery, backend, or frontend container state

## Prerequisites

- `KUBECONFIG=~/.kube/config-staging` exists and is valid
- kubectl context `staging-cluster` is configured
- Namespace: `meeting-automation-staging`

## Procedure

### 1. Quick Pod Status Overview

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster get pods -n meeting-automation-staging -o wide
```

### 2. Get Backend Pod Name

The backend pod name changes on each rollout. Always resolve dynamically:

```bash
export KUBECONFIG=~/.kube/config-staging
BACKEND_POD=$(kubectl get pods -l app=backend -n meeting-automation-staging --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
echo "Backend pod: $BACKEND_POD"
```

Or the shorter variant (most recent pod):

```bash
export KUBECONFIG=~/.kube/config-staging
BACKEND_POD=$(kubectl --context=staging-cluster get pod -n meeting-automation-staging -l app=backend -o jsonpath='{.items[-1].metadata.name}')
```

### 3. Get Any Pod by App Label

```bash
export KUBECONFIG=~/.kube/config-staging
POD=$(kubectl --context=staging-cluster get pod -n meeting-automation-staging -l app=<LABEL> -o jsonpath='{.items[0].metadata.name}')
echo "Pod: $POD"
```

Common labels: `backend`, `frontend`, `celery-worker`, `n8n-staging`, `livekit-server-staging`, `livekit-egress-staging`, `openhive`, `alert-adapter`

### 4. Exec Into Backend Pod (Python)

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster exec -n meeting-automation-staging deployment/backend -- python3 -c "
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT 1'))
        print(result.scalar())

asyncio.run(main())
"
```

### 5. Query Staging DB via PostgreSQL Pod

```bash
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c "SELECT version_num FROM alembic_version;"
```

For output-only mode (no headers):

```bash
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -t -c "SELECT count(*) FROM meetings;"
```

### 6. Check Backend Logs

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster logs -n meeting-automation-staging deployment/backend --tail=50
```

### 7. Check Celery Worker Logs

```bash
export KUBECONFIG=~/.kube/config-staging
CELERY_POD=$(kubectl get pod -l app=celery-worker -n meeting-automation-staging -o jsonpath='{.items[0].metadata.name}')
kubectl --context=staging-cluster logs -n meeting-automation-staging $CELERY_POD --tail=50
```

### 8. Restart Backend Deployment

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster rollout restart deployment/backend -n meeting-automation-staging 2>&1
kubectl --context=staging-cluster rollout status deployment/backend -n meeting-automation-staging --timeout=60s 2>&1
```

### 9. Check Alembic Migration Version

```bash
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c "SELECT version_num FROM alembic_version;"
```

### 10. Check n8n API Key and Workflow Status

```bash
N8N_API_KEY=$(kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get secret n8n-secrets -n meeting-automation-staging -o jsonpath='{.data.N8N_API_KEY}' 2>/dev/null | base64 -d)
echo "n8n API Key: ${N8N_API_KEY:0:20}..."
```

## Stopping Condition

- Pod status visible and interpreted
- Log output captured and analyzed
- DB query result returned
- Restart completed (rollout status "successfully rolled out")

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| Hardcoded pod names (change on rollout) | Always resolve dynamically with `kubectl get pod -l app=X -o jsonpath` |
| Wrong kubeconfig context | Always set `KUBECONFIG=~/.kube/config-staging` AND `--context=staging-cluster` |
| `kubectl exec` with wrong pod selector | Verify pod exists first with `kubectl get pods -l app=<label>` |
| DB queries without quoting mixed-case columns | Use double quotes: `SELECT "workflowId" FROM workflow_history` |
| Forgetting namespace flag | Always include `-n meeting-automation-staging` |

## Notes

- User communicates in German — match language in responses
- Pod names change on every rollout; never hardcode
- Backend Python exec uses `AsyncSessionLocal` (asyncpg driver)
- PostgreSQL pod is a StatefulSet: `postgres-staging-0`
- MinIO pod is a StatefulSet: `minio-staging-0`
- For E2E tests, use `docker-compose.e2e.yml` (NOT the staging cluster)
