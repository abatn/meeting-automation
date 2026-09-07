# Production vs Staging — Full Resource Comparison

**Date:** 2026-09-03
**Status:** 🔴 Production has critical capacity gaps
**Production:** 169.58.83.32 (Contabo, AMD64)
**Staging:** 158.180.18.110 (OCI, ARM64)

---

## 1. Node Hardware

| Resource | Production (Contabo) | Staging (OCI) | Difference |
|----------|----------------------|---------------|------------|
| Architecture | AMD64 (x86_64) | ARM64 (aarch64) | Different! |
| CPU Model | AMD EPYC 2.0GHz | ARM Cortex-A76 | ARM faster single-thread |
| CPU Cores | 8 | 4 | Prod +100% |
| Memory | 24GB | 22GB | Prod +9% |
| Load Average | 6.02 (75%) | ~1.0 (25%) | Prod 6x higher |
| k3s Version | v1.36.2+k3s1 | v1.30+ | — |
| Container Runtime | containerd 2.3.2 | containerd | — |

---

## 2. Pod Resource Allocation (Per Container)

| Component | Production | Staging | Gap |
|-----------|------------|---------|-----|
| backend | 100m-500m CPU, 256Mi-1Gi | 100m-500m CPU, 256Mi-1Gi, 200Mi-1Gi eph | Prod missing eph |
| celery-beat | 50m-200m CPU, 128Mi-512Mi | — | — |
| celery-worker-pro | 200m-1 CPU, 2Gi-6Gi | 200m-1 CPU, 2Gi-6Gi | ✅ Same |
| frontend | 50m-200m CPU, 64Mi-128Mi | — | — |
| livekit-egress | 500m-2 CPU, 512Mi-2Gi | 500m-2 CPU, 512Mi-2Gi, 200Mi-1Gi eph | Prod missing eph |
| livekit-server | 500m-1 CPU, 512Mi-1Gi | 100m-500m CPU, 256Mi-512Mi | Prod 2x CPU+RAM |
| onlyoffice | 200m-1 CPU, 512Mi-2Gi | — | — |
| redis | 100m-500m CPU, 256Mi-512Mi | 100m-500m CPU, 256Mi-512Mi | ✅ Same |

---

## 3. Production Resource Overcommitment

| Resource | Requests | Limits | Overcommit Ratio | Status |
|----------|----------|--------|------------------|--------|
| CPU | 3200m (42%) | 13400m (178%) | 4.2x | 🔴 CRITICAL |
| Memory | 7208Mi (31%) | 23290Mi (101%) | 3.2x | 🟡 WARNING |
| Ephemeral | 500Mi (0%) | 2Gi (0%) | 4x | ✅ OK |

**Risk:** CPU is overcommitted 4.2x. If multiple pods burst simultaneously, OOM/CPU throttling occurs.

---

## 4. Capacity Gaps Identified

| Gap | Impact | Severity |
|-----|--------|----------|
| No metrics-server | HPA cannot scale based on CPU | 🔴 CRITICAL |
| No ephemeral-storage on 8/10 deployments | Pods can fill disk → node pressure | 🟡 WARNING |
| CPU overcommitted 4.2x | Pipeline pods compete for CPU → slow inference | 🟡 WARNING |
| Celery worker: 1 replica (should be 2) | Single point of failure, no parallelism | 🟡 WARNING |
| LiveKit Egress: v1.8.4 (not v1.9.0) | Staging already upgraded | 🟢 LOW |
| No ResourceQuota | No namespace-level guardrails | 🟢 LOW |

---

## 5. Pipeline Performance Impact

| Stage | Staging (ARM64) | Production (AMD64) | Ratio | Root Cause |
|-------|-----------------|---------------------|-------|------------|
| ONNX Embed | 27s | 115s | 4.3x | CPU throttling (4.2x overcommit) |
| Sentinel LLM | 56s | CRASH | — | SIGSEGV from memory pressure |
| FFmpeg | 3s | 27s | 9x | CPU starvation |
| **Total** | **113s** | **CRASH** | — | — |

**Root Cause:** Production CPU is overcommitted 4.2x. When ONNX (8 threads) and Sentinel (2 threads) run simultaneously, they fight for 1 CPU core each → CPU throttling → slow inference → SIGSEGV.

---

## 6. Recommended Fixes

| Priority | Fix | Command |
|----------|-----|---------|
| 🔴 P0 | Install metrics-server | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` |
| 🔴 P0 | Reduce CPU limits or increase cores | Remove 500m from non-critical pods |
| 🟡 P1 | Scale celery-worker-pro to 2 | `kubectl scale deployment celery-worker-pro --replicas=2` |
| 🟡 P1 | Add ephemeral-storage to all deployments | Update YAML files |
| 🟡 P1 | Fix CNPG CRD issue | Check CNPG operator version |
| 🟢 P2 | Upgrade LiveKit Egress to v1.9.0 | Update image tag |

---

## 7. Verification Commands

```bash
# Production
ssh root@169.58.83.32 "kubectl describe node contabo-prod | grep -A 20 'Allocated resources:'"
ssh root@169.58.83.32 "kubectl top nodes 2>/dev/null || echo 'metrics-server not installed'"
ssh root@169.58.83.32 "lscpu | grep -E 'CPU\(s\)|Model name'"

# Staging (requires SSH key)
ssh root@158.180.18.110 "kubectl describe node | grep -A 20 'Allocated resources:'"
ssh root@158.180.18.110 "kubectl top nodes"
ssh root@158.180.18.110 "lscpu | grep -E 'CPU\(s\)|Model name'"
```
