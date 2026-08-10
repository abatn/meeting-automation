# Staging Recovery Plan — 2026-07-28

## Context
- **E2E Pipeline** `30376328324` failed at Deploy Staging (rollout timeout 600s)
- **Date**: 2026-07-28, ~16:00 UTC

## Root Cause Analysis (3 Iterations)

### Iteration 1 (WRONG): CNPG DB not ready
- ~~DB recovering when backend init tried to connect~~ — DB was 1 instance, this was expected (BAUPLAN: "CNPG: 1 Instance")

### Iteration 2 (WRONG): Docker Hub Pull-Secret
- Added `dockerhub-pull-secret` + `imagePullSecrets` to all deployments
- **Result**: Frontend rollout ✅ succeeded. But E2E deploy still failed after 600s.

### Iteration 3 (CORRECT): Pod-Garbage-Collection-Blockade
**2242 dead/zombie pods across ALL namespaces consume ephemeral storage → `DiskPressure: True` → kubelet evicts EVERY new pod → rollout never completes.**

**Evidence (verified via `kubectl`):**

| Metric | Value |
|--------|-------|
| Node condition `DiskPressure` | **True** |
| Total pods on node | **2330** |
| Running pods | **4** |
| Dead/zombie pods | **2242** (Completed 782, Error 745, ContainerStatusUnknown 572, Evicted 139, Init:Error 41) |

| Namespace | Dead Pods | Total |
|-----------|-----------|-------|
| argocd | 627 | 637 |
| longhorn-system | 632 | 639 |
| monitoring | 366 | 372 |
| cert-manager | 226 | 229 |
| velero | 148 | 149 |
| cnpg-system | 133 | 134 |
| ingress-nginx | 110 | 111 |

**Why it recurs (3rd time):** kubelet's Garbage Collector does NOT automatically delete `Error`/`ContainerStatusUnknown`/`Evicted` pods. Only `Completed` pods are cleaned. Dead pods accumulate → disk fills → `DiskPressure: True` → cascade eviction.

**Eviction event pattern:**
```
pod/frontend-57dd667c58-fnb8h  Evicted  "The node was low on resource: ephemeral-storage. 
  Threshold: 9815929797, available: 20337648Ki. 
  Container frontend was using 32Ki, request is 0, has larger consumption."
```
→ Pod gets evicted → new pod created → evicted again → rollout timeout.

## Plan (4 Steps)

### Step 1: Delete ALL dead/zombie pods (SOFORT)
```bash
# Delete all pods in non-Running/Pending/PodInitializing states across ALL namespaces
kubectl get pods --all-namespaces --no-headers | \
  awk '$4 ~ /^(Completed|Error|Evicted|ContainerStatusUnknown|Init:Error|Init:ContainerStatusUnknown|CrashLoopBackOff|Unknown|ImagePullBackOff|ErrImagePull|CreateContainerConfigError|RunContainerError)$/ {print $1, $2}' | \
  while read ns pod; do
    kubectl delete pod "$pod" -n "$ns" --grace-period=0 --force 2>/dev/null
  done
```
- **Verify**: `kubectl get pods --all-namespaces --no-headers | wc -l` should be ≤ 30
- **Verify**: `kubectl describe node instance-20260329-0846 | grep DiskPressure` should show `False`
- **Revert**: N/A (deleting dead pods is always safe)

### Step 2: Check if unused namespaces can be removed
- `argocd` (627 dead) — needed?
- `longhorn-system` (632 dead) — single-node k3s, longhorn not functional
- `velero` (148 dead) — backup tool, needed?
- `monitoring` (366 dead) — Prometheus/Grafana, needed?
- **Revert**: If namespace deleted accidentally, re-apply from YAML

### Step 3: Verify staging cluster recovers
```bash
# After cleanup:
kubectl get pods --all-namespaces --no-headers | awk '{print $4}' | sort | uniq -c | sort -rn
# Should show mostly Running

kubectl describe node instance-20260329-0846 | grep -A 3 "Conditions:"
# DiskPressure should be False

# All staging deployments should recover
kubectl get deploy -n meeting-automation-staging -o custom-columns='NAME:.metadata.name,READY:.status.readyReplicas,DESIRED:.spec.replicas'
```
- **Expected**: 16/16 pods Running in meeting-automation-staging
- **Revert**: If pods don't recover, `kubectl rollout restart deployment/<name> -n meeting-automation-staging`

### Step 4: Trigger CI retry
```bash
cd /home/opc/meeting-automation
git commit --allow-empty -m "ci: retry staging deploy after cleanup"
git push origin main
```
- **Verify**: `gh run list --limit 3` shows new runs
- **Verify**: E2E deploy job passes `kubectl rollout status`
- **Revert**: `gh run cancel <run-id>` if something goes wrong

## Rollback Strategy
| Scenario | Action |
|----------|--------|
| Cleanup deleted running pods | `kubectl rollout restart deployment/<name> -n meeting-automation-staging` |
| CI deploy fails again | Check `kubectl describe node` for DiskPressure, re-run Step 1 |
| Namespaces accidentally deleted | Re-apply from `infrastructure/kubernetes/staging/` YAMLs |
| DiskPressure returns | Repeat Step 1 + check `/var/log/pods` size on node |

## Prevention (Future)
| # | Action | Priority |
|---|--------|----------|
| 1 | Add CI step: check `DiskPressure` before deploy | High |
| 2 | Add kubelet `--eviction-minimum-reclaim` config | Medium |
| 3 | CronJob to delete `Error`/`Evicted` pods daily | Medium |
| 4 | Evaluate if argocd/longhorn/velero namespaces are needed | Low |

## Files Changed
- `.github/workflows/e2e-tests.yml (DEPRECATED)` (Docker Hub pull secret, timeout 600s, celery rollout waits)
- `docs/STAGING_RECOVERY_PLAN_2026-07-28.md` (this file)
