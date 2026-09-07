# Deployment Comparison: Production vs Staging

**Date:** 2026-09-03
**Workflow:** `.github/workflows/e2e-tests.yml`

---

## Summary

Production deployment is **missing critical infrastructure components** that staging has:

| Component | Staging | Production | Impact |
|-----------|---------|------------|--------|
| metrics-server | ✅ Deployed | ❌ Missing | HPA cannot scale based on CPU |
| KEDA | ✅ Deployed | ❌ Missing | No event-driven scaling |
| Velero | ✅ Deployed | ❌ Missing | No backup/restore |
| Network Policies | 14+ policies | 7 policies | Weaker security |
| LiveKit Egress | v1.9.0 | v1.8.4 | Staging ahead |

---

## Detailed Comparison

### 1. Staging Deployment (e2e-tests.yml Job 2)

**Namespace:** `meeting-automation-staging`

**Resources Applied:**
- namespace.yaml
- backend-secrets.yaml
- backend-config.yaml
- backend-deployment.yaml
- celery-beat-deployment.yaml
- celery-worker-deployment.yaml
- celery-worker-hpa.yaml
- celery-worker-pro-deployment.yaml
- cert-manager-acme-solver-policy.yaml
- cnpg-cluster.yaml
- frontend-deployment.yaml
- frontend-nginx-config.yaml
- ingress-staging.yaml
- keda-rabbitmq-networkpolicy.yaml
- keda-scaledobjects.yaml
- livekit-configmap.yaml
- livekit-egress-configmap.yaml
- livekit-egress-deployment.yaml
- livekit-secrets.yaml
- livekit-server-deployment.yaml
- minio-secrets.yaml
- minio-statefulset.yaml
- n8n-deployment.yaml
- n8n-ingress.yaml
- n8n-nodeport-policy.yaml
- n8n-secrets.yaml
- n8n-service-nodeport.yaml
- network-policies.yaml
- onlyoffice-custom-config.yaml
- onlyoffice-deployment.yaml
- onlyoffice-secrets.yaml
- postgres-backup-cronjob.yaml
- postgres-secrets.yaml
- postgres-statefulset.yaml
- rabbitmq-secrets.yaml
- rabbitmq-statefulset.yaml
- redis-deployment.yaml
- redis-secrets.yaml
- sentinel-models-claim.yaml

**System Resources (kube-system):**
- ephemeral-storage-cleanup-cronjob.yaml
- pod-garbage-collector-cronjob.yaml
- metrics-server-patch.yaml

**Velero (velero namespace):**
- velero-backup-repository.yaml

### 2. Production Deployment (e2e-tests.yml Job 3)

**Namespace:** `meeting-automation`

**Resources Applied:**
- backend-config.yaml
- frontend-nginx-config.yaml
- livekit-configmap.yaml
- livekit-egress-configmap.yaml
- onlyoffice-custom-config.yaml
- ingress-prod.yaml
- network-policies.yaml

**Secrets (only if not exists):**
- backend-secrets
- postgres-secrets
- redis-secrets
- minio-secrets
- rabbitmq-secrets
- livekit-secrets
- n8n-secrets
- onlyoffice-secrets

**System Resources (kube-system):**
- ephemeral-storage-cleanup-cronjob.yaml
- pod-garbage-collector-cronjob.yaml

---

## Missing Production Resources

| File | Purpose | Impact |
|------|---------|--------|
| keda-scaledobjects.yaml | Event-driven pod scaling | No KEDA scaling |
| keda-rabbitmq-networkpolicy.yaml | KEDA network access | KEDA cannot function |
| velero-backup-repository.yaml | Backup configuration | No disaster recovery |
| metrics-server.yaml | CPU metrics for HPA | HPA cannot scale based on CPU |
| cert-manager-acme-solver-policy.yaml | TLS certificate policy | No automatic TLS |
| n8n-nodeport-policy.yaml | n8n NodePort access | n8n inaccessible |
| n8n-service-nodeport.yaml | n8n NodePort service | n8n inaccessible |
| sentinel-models-claim.yaml | Sentinel model storage | Model storage issues |

---

## Recommended Fixes

1. **Add metrics-server to production workflow**
2. **Add KEDA to production workflow**
3. **Add Velero to production workflow**
4. **Sync LiveKit Egress version (v1.8.4 → v1.9.0)**
5. **Add missing network policies**
6. **Add sentinel-models-claim.yaml**

---

## Production vs Staging Resource Allocation

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
