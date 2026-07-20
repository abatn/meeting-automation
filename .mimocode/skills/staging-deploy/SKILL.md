# SKILL: Staging Deployment (Build → k3s Import → Rollout)

End-to-end workflow for building Docker images and deploying them to the staging k3s cluster. Covers the complete cycle: build, tag, save, import to k3s containerd, update deployment, and verify rollout.

**Description:** Packages the repeated build-and-deploy pattern used across multiple sessions. Critical: follows the AGENTS.md rule that ONLY pruning unused images is allowed — never `docker system prune` or `k3s ctr images prune`.

## When to Use

- User says "deploy to staging", "staging deploy", "build und deploy"
- After code changes that need to be tested in the staging environment
- When CI/CD pipeline needs manual intervention
- After fixing a bug that requires staging verification

## Prerequisites

- Docker images build successfully
- `KUBECONFIG=~/.kube/config-staging` exists
- kubectl context `staging-cluster` configured
- k3s containerd accessible via `sudo /usr/local/bin/k3s ctr`

## Procedure

### 1. Build Backend Image

```bash
cd /home/opc/meeting-automation
docker build -t meeting-automation-backend:staging -f backend/Dockerfile backend/
```

### 2. Build Frontend Image (if changed)

```bash
cd /home/opc/meeting-automation/frontend
npm run build 2>&1 | tail -3
cd /home/opc/meeting-automation
docker build -t meeting-automation-frontend:staging -f frontend/Dockerfile frontend/
```

### 3. Tag with Timestamp

```bash
TIMESTAMP=$(date +%Y%m%d%H%M%S)
docker tag meeting-automation-backend:staging meeting-automation-backend:v${TIMESTAMP}
```

### 4. Save and Import to k3s Containerd

```bash
TIMESTAMP=$(date +%Y%m%d%H%M%S)
cd /home/opc/meeting-automation
docker tag meeting-automation-backend:staging meeting-automation-backend:v${TIMESTAMP}
docker save meeting-automation-backend:v${TIMESTAMP} | sudo /usr/local/bin/k3s ctr -n k8s.io images import -
```

### 5. Update Deployment

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster set image deployment/backend backend=meeting-automation-backend:v${TIMESTAMP} -n meeting-automation-staging
```

### 6. Wait for Rollout

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster rollout status deployment/backend -n meeting-automation-staging --timeout=120s
```

### 7. Verify New Image is Running

```bash
export KUBECONFIG=~/.kube/config-staging
kubectl --context=staging-cluster get pods -n meeting-automation-staging -l app=backend -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,STATUS:.status.phase'
```

### 8. Repeat for Other Services (if needed)

Same pattern for frontend, celery-worker, etc.:
```bash
# Frontend
docker tag meeting-automation-frontend:staging meeting-automation-frontend:v${TIMESTAMP}
docker save meeting-automation-frontend:v${TIMESTAMP} | sudo /usr/local/bin/k3s ctr -n k8s.io images import -
kubectl --context=staging-cluster set image deployment/frontend frontend=meeting-automation-frontend:v${TIMESTAMP} -n meeting-automation-staging
```

## Complete One-Shot Command

For backend-only deploy:

```bash
TIMESTAMP=$(date +%Y%m%d%H%M%S) && \
cd /home/opc/meeting-automation && \
docker build -t meeting-automation-backend:staging -f backend/Dockerfile backend/ 2>&1 | tail -3 && \
docker tag meeting-automation-backend:staging meeting-automation-backend:v${TIMESTAMP} && \
docker save meeting-automation-backend:v${TIMESTAMP} | sudo /usr/local/bin/k3s ctr -n k8s.io images import - && \
export KUBECONFIG=~/.kube/config-staging && \
kubectl --context=staging-cluster set image deployment/backend backend=meeting-automation-backend:v${TIMESTAMP} -n meeting-automation-staging && \
kubectl --context=staging-cluster rollout status deployment/backend -n meeting-automation-staging --timeout=120s
```

## Stopping Condition

- Docker image built successfully
- Image imported to k3s containerd (no `ErrImagePull`)
- Deployment updated and rollout complete
- New pod running with correct image tag

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| **FORBIDDEN**: `docker system prune`, `docker image prune`, `k3s ctr images prune --all` | These delete images k3s depends on → all pods ImagePullBackOff |
| Image path mismatch (`docker.io/library/...` vs `docker.io/batnini/...`) | Always use `meeting-automation-backend:staging` (local tag), not registry path |
| `ErrImagePull` after deploy | Image not in k3s containerd — re-run `k3s ctr images import` |
| Wrong image name in `kubectl set image` | Verify with `kubectl get deployment backend -o jsonpath='{.spec.template.spec.containers[0].image}'` |
| Rollout hangs | Check `kubectl describe pod <pod>` for Events — usually image pull or readiness probe |
| Forgetting `IfNotPresent` imagePullPolicy | k3s defaults to `Always` for `docker.io/` — local images need `IfNotPresent` in deployment spec |

## Notes

- The deploy pattern is: build → `k3s ctr -n k8s.io images import` → `kubectl set image` → `kubectl rollout restart`
- NEVER delete images during deploy — only prune images NOT referenced by any running deployment
- Timestamp tagging ensures unique image versions for rollback
- For Celery workers, also check queue routing (AGENTS.md: `apply_async(queue='transcription_gratuit')`)
- After deploy, verify with `kubectl get pods -o custom-columns=IMAGE:.spec.containers[0].image`
