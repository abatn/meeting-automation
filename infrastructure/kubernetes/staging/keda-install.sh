#!/bin/bash
# KEDA Installation + Hardcoded HPA entfernen
# Fuer Staging (OCI, ARM64)
# Erstellt: 2026-08-14

set -e

echo "=== 1. KEDA installieren ==="
helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null || true
helm repo update

helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --set operator.replicaCount=1 \
  --set metricsServer.replicaCount=1 \
  --wait --timeout 5m

echo "=== 2. Warte auf KEDA Pods ==="
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=keda-operator -n keda --timeout=120s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=keda-metrics-server -n keda --timeout=120s

echo "=== 3. KEDA Version pruefen ==="
kubectl get deployment keda-operator -n keda -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""

echo "=== 4. Hardcoded HPA entfernen ==="
kubectl delete hpa celery-worker-hpa -n meeting-automation-staging --ignore-not-found

echo "=== 5. KEDA ScaledObject fuer Celery GRATUIT ==="
cat <<EOF | kubectl apply -f -
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-gratuit
  namespace: meeting-automation-staging
spec:
  scaleTargetRef:
    name: celery-worker-staging
  minReplicaCount: 0
  maxReplicaCount: 10
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: rabbitmq
      metadata:
        host: amqp://rabbit_user:rabbit_password@rabbitmq-staging.meeting-automation-staging.svc.cluster.local:5672//
        queueName: transcription_gratuit
        queueLength: "5"
        mode: QueueLength
EOF

echo "=== 6. KEDA ScaledObject fuer Celery PRO ==="
cat <<EOF | kubectl apply -f -
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-pro
  namespace: meeting-automation-staging
spec:
  scaleTargetRef:
    name: celery-worker-pro-staging
  minReplicaCount: 0
  maxReplicaCount: 10
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: rabbitmq
      metadata:
        host: amqp://rabbit_user:rabbit_password@rabbitmq-staging.meeting-automation-staging.svc.cluster.local:5672//
        queueName: transcription_pro
        queueLength: "5"
        mode: QueueLength
EOF

echo "=== 7. KEDA ScaledObject fuer LiveKit Egress ==="
cat <<EOF | kubectl apply -f -
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: livekit-egress
  namespace: meeting-automation-staging
spec:
  scaleTargetRef:
    name: livekit-egress
  minReplicaCount: 1
  maxReplicaCount: 5
  pollingInterval: 30
  cooldownPeriod: 120
  triggers:
    - type: cpu
      metricType: Utilization
      metadata:
        value: "80"
EOF

echo "=== 8. Verifikation ==="
echo "--- KEDA ScaledObjects ---"
kubectl get scaledobject -n meeting-automation-staging
echo ""
echo "--- KEDA TriggerAuthentication ---"
kubectl get triggerauthentication -n meeting-automation-staging 2>/dev/null || echo "No TriggerAuthentications"
echo ""
echo "--- HPA (sollte leer sein) ---"
kubectl get hpa -n meeting-automation-staging 2>&1

echo "=== KEDA Installation abgeschlossen ==="
