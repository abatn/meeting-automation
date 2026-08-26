#!/bin/bash
# 01-setup-k8s.sh — Configure K8s context + Secrets + Docker Hub Pull Secret
# Env: KUBECONFIG
set -e

NAMESPACE="${NAMESPACE:-meeting-automation-staging}"
export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== Configure K8s Context ==="
CONTEXT=$(kubectl config get-contexts -o name | head -1)
if [ -z "$CONTEXT" ]; then
  echo "❌ No contexts found in kubeconfig"
  exit 1
fi
echo "Using context: $CONTEXT"
kubectl config use-context "$CONTEXT"
kubectl get namespace "$NAMESPACE" || kubectl apply -f infrastructure/kubernetes/staging/namespace.yaml

echo "=== Create/Update Staging Secrets ==="
kubectl create secret generic e2e-test-user \
  --namespace "$NAMESPACE" \
  --from-literal=E2E_TEST_USER_EMAIL="${E2E_TEST_USER_EMAIL}" \
  --from-literal=E2E_TEST_USER_PASSWORD="${E2E_TEST_USER_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic backend-api-keys-staging \
  --namespace "$NAMESPACE" \
  --from-literal=MISTRAL_API_KEY="${MISTRAL_API_KEY}" \
  --from-literal=GLADIA_API_KEY="${GLADIA_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== Ensure Docker Hub Pull Secret ==="
kubectl create secret docker-registry dockerhub-pull-secret \
  --namespace "$NAMESPACE" \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=batnini \
  --docker-password="${DOCKERHUB_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -

# OnlyOffice Secrets (JWT + Secure Link)
kubectl apply -f infrastructure/kubernetes/staging/onlyoffice-secrets.yaml 2>/dev/null || echo "⚠️ onlyoffice-secrets apply failed"
for deploy in $(kubectl get deploy -n "$NAMESPACE" -o name 2>/dev/null); do
  HAS_SECRET=$(kubectl get "$deploy" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.imagePullSecrets[?(@.name=="dockerhub-pull-secret")].name}' 2>/dev/null)
  if [ -z "$HAS_SECRET" ]; then
    kubectl patch "$deploy" -n "$NAMESPACE" --type=json \
      -p='[{"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[{"name":"dockerhub-pull-secret"}]}]' 2>&1 || true
  fi
done
echo "✅ K8s context + Secrets + Docker Hub Pull Secret ready"
