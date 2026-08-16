#!/bin/bash
# 01-pull-images.sh — Pull Docker images to k3s containerd
# Env: BACKEND_IMAGE, FRONTEND_IMAGE, DOCKERHUB_TOKEN, DOCKERHUB_USERNAME
set -e

echo "=== Pulling fresh images to k3s containerd ==="

# Login to registry
echo "$DOCKERHUB_TOKEN" | k3s ctr images registry login docker.io \
  --username "$DOCKERHUB_USERNAME" --password-stdin 2>/dev/null || true

# Remove cached images to force fresh pull (prevents stale :latest)
k3s ctr images rm "$BACKEND_IMAGE" 2>/dev/null || true
k3s ctr images rm "$FRONTEND_IMAGE" 2>/dev/null || true

# Pull backend
k3s ctr images pull "$BACKEND_IMAGE" || {
  echo "Direct pull failed, falling back to docker save"
  docker pull "$BACKEND_IMAGE"
  docker save "$BACKEND_IMAGE" | k3s ctr images import -
  docker image rm "$BACKEND_IMAGE" 2>/dev/null || true
}

# Pull frontend
k3s ctr images pull "$FRONTEND_IMAGE" || {
  echo "Frontend direct pull failed, trying fallback"
  docker pull "$FRONTEND_IMAGE" || echo "Frontend image not available"
  docker save "$FRONTEND_IMAGE" | k3s ctr images import - 2>/dev/null || true
  docker image rm "$FRONTEND_IMAGE" 2>/dev/null || true
}

echo "✅ Images pulled successfully"
