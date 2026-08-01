#!/bin/bash
set -u

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="meeting-automation-staging"

echo -e "${BLUE}🔍 Meeting Automation Staging System Status${NC}"
echo "================================================"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# 1. Disk Usage
echo -e "${BLUE}[1] DISK${NC}"
df -h / | tail -1 | awk '{printf "   Used: %s / %s (%s) — Avail: %s\n", $3, $2, $5, $4}'
DISK_PCT=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%') || DISK_PCT=0
if [ "$DISK_PCT" -gt 90 ]; then
    echo -e "   ${RED}⚠️  CRITICAL: ${DISK_PCT}% — DiskPressure risk!${NC}"
elif [ "$DISK_PCT" -gt 80 ]; then
    echo -e "   ${YELLOW}⚠️  WARNING: ${DISK_PCT}% — monitor closely${NC}"
else
    echo -e "   ${GREEN}✅ OK: ${DISK_PCT}%${NC}"
fi
echo ""

# 2. k3s Node Status
echo -e "${BLUE}[2] k3s NODE${NC}"
kubectl get nodes --no-headers 2>/dev/null | while read line; do
    STATUS=$(echo "$line" | awk '{print $2}')
    TAINTS=$(kubectl describe node 2>/dev/null | grep "Taints:" | head -1 | awk '{print $2}')
    if [ "$STATUS" = "Ready" ] && [ -z "$TAINTS" ]; then
        echo -e "   ${GREEN}✅ Node: Ready, no taints${NC}"
    elif [ "$STATUS" = "Ready" ]; then
        echo -e "   ${YELLOW}⚠️  Node: Ready but has taints: $TAINTS${NC}"
    else
        echo -e "   ${RED}❌ Node: $STATUS${NC}"
    fi
done
echo ""

# 3. k3s Pods
echo -e "${BLUE}[3] k3s PODS ($NAMESPACE)${NC}"
TOTAL=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -v 'Succeeded' | wc -l)
RUNNING=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -c 'Running')
PENDING=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -c 'Pending')
FAILED=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -c 'Failed')
ERROR=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -c 'Error')
BACKOFF=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -c 'BackOff')

echo "   Total: $TOTAL | Running: $RUNNING | Pending: $PENDING | Failed/Error: $((FAILED+ERROR)) | BackOff: $BACKOFF"

if [ "$RUNNING" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo -e "   ${GREEN}✅ All pods running${NC}"
elif [ "$FAILED" -gt 0 ] || [ "$ERROR" -gt 0 ]; then
    echo -e "   ${RED}⚠️  $((FAILED+ERROR)) pods failed/error${NC}"
    kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -E 'Failed|Error' | awk '{printf "   → %s (%s)\n", $1, $3}'
else
    echo -e "   ${YELLOW}⚠️  Some pods not running${NC}"
fi
echo ""

# 4. Core Services Check
echo -e "${BLUE}[4] CORE SERVICES${NC}"
for SVC in backend celery-worker-staging celery-worker-pro-staging celery-beat-staging frontend; do
    READY=$(kubectl get deployment $SVC -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    DESIRED=$(kubectl get deployment $SVC -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [ "$READY" = "$DESIRED" ] && [ "$READY" != "0" ]; then
        echo -e "   ${GREEN}✅ $SVC: $READY/$DESIRED${NC}"
    else
        echo -e "   ${RED}❌ $SVC: ${READY:-0}/$DESIRED${NC}"
    fi
done
echo ""

# 5. RabbitMQ Queues
echo -e "${BLUE}[5] RABBITMQ QUEUES${NC}"
RABBIT_POD=$(kubectl get pod -n $NAMESPACE -l app=rabbitmq --no-headers -o custom-columns=NM:.metadata.name 2>/dev/null | head -1)
if [ -z "$RABBIT_POD" ]; then
    echo -e "   ${RED}❌ RabbitMQ pod not found${NC}"
else
QUEUES=$(kubectl exec "$RABBIT_POD" -n $NAMESPACE -- rabbitmqctl list_queues name messages consumers 2>/dev/null | grep -E '^celery |^transcription |^transcription_pro |^transcription_gratuit |^email |^maintenance ')
if [ -n "$QUEUES" ]; then
    echo "$QUEUES" | while read line; do
        NAME=$(echo "$line" | awk '{print $1}')
        MSGS=$(echo "$line" | awk '{print $2}')
        CONS=$(echo "$line" | awk '{print $3}')
        if [ "$MSGS" -gt 0 ]; then
            echo -e "   ${YELLOW}⚠️  $NAME: $MSGS msgs, $CONS consumers${NC}"
        else
            echo -e "   ${GREEN}✅ $NAME: 0 msgs, $CONS consumers${NC}"
        fi
    done
else
    echo -e "   ${RED}❌ Cannot connect to RabbitMQ${NC}"
fi
fi
echo ""

# 6. Database
echo -e "${BLUE}[6] DATABASE${NC}"
DB_STATUS=$(kubectl exec meeting-db-1 -n $NAMESPACE -c postgres -- pg_isready -U meeting_user 2>/dev/null)
if [[ "$DB_STATUS" == *"accepting connections"* ]]; then
    echo -e "   ${GREEN}✅ PostgreSQL: accepting connections${NC}"
    MEETINGS=$(kubectl exec meeting-db-1 -n $NAMESPACE -c postgres -- env PGPASSWORD=meeting_password psql -h 127.0.0.1 -U meeting_user -d meeting_db_staging -t -A -c "SELECT count(*) FROM meetings;" 2>/dev/null)
    RECORDINGS=$(kubectl exec meeting-db-1 -n $NAMESPACE -c postgres -- env PGPASSWORD=meeting_password psql -h 127.0.0.1 -U meeting_user -d meeting_db_staging -t -A -c "SELECT count(*) FROM recordings;" 2>/dev/null)
    USERS=$(kubectl exec meeting-db-1 -n $NAMESPACE -c postgres -- env PGPASSWORD=meeting_password psql -h 127.0.0.1 -U meeting_user -d meeting_db_staging -t -A -c "SELECT count(*) FROM users;" 2>/dev/null)
    echo "   Meetings: $MEETINGS | Recordings: $RECORDINGS | Users: $USERS"
else
    echo -e "   ${RED}❌ PostgreSQL: not ready${NC}"
fi
echo ""

# 7. Endpoints
echo -e "${BLUE}[7] ENDPOINTS${NC}"
BACKEND_HTTP=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' https://staging.meeting-automation.com/api/v1/auth/me 2>/dev/null)
FRONTEND_HTTP=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' https://staging.meeting-automation.com/ 2>/dev/null)
OO_HTTP=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' https://staging.meeting-automation.com/healthcheck 2>/dev/null)

[ "$BACKEND_HTTP" = "401" ] && echo -e "   ${GREEN}✅ Backend API: $BACKEND_HTTP (auth required)${NC}" || echo -e "   ${RED}❌ Backend API: $BACKEND_HTTP${NC}"
[ "$FRONTEND_HTTP" = "200" ] && echo -e "   ${GREEN}✅ Frontend: $FRONTEND_HTTP${NC}" || echo -e "   ${RED}❌ Frontend: $FRONTEND_HTTP${NC}"
[ "$OO_HTTP" = "200" ] && echo -e "   ${GREEN}✅ OnlyOffice: $OO_HTTP${NC}" || echo -e "   ${RED}❌ OnlyOffice: $OO_HTTP${NC}"
echo ""

# 8. k3s Containerd Images
echo -e "${BLUE}[8] k3s IMAGES${NC}"
IMG_COUNT=$(sudo /usr/local/bin/k3s ctr -n k8s.io images list -q 2>/dev/null | wc -l)
CONTAINERD_SIZE=$(sudo du -sh /var/lib/rancher/k3s/agent/containerd/ 2>/dev/null | awk '{print $1}')
STORAGE_SIZE=$(sudo du -sh /var/lib/rancher/k3s/storage/ 2>/dev/null | awk '{print $1}')
echo "   Images: $IMG_COUNT | containerd: $CONTAINERD_SIZE | storage: $STORAGE_SIZE"
echo ""

# 9. Safe Cleanup Options
echo -e "${BLUE}[9] CLEANUP OPPORTUNITIES${NC}"
JOURNAL_SIZE=$(sudo journalctl --disk-usage 2>/dev/null | grep -oP '[\d.]+[GMK]' | head -1)
echo "   Journal: ${JOURNAL_SIZE:-unknown}"

# Check for unreferenced k3s content
UNREF_CONTENT=$(sudo /usr/local/bin/k3s ctr -n k8s.io content ls -q 2>/dev/null | wc -l)
echo "   k3s content blobs: $UNREF_CONTENT"

# Docker build cache
BUILD_CACHE=$(docker system df 2>/dev/null | grep "Build Cache" | awk '{print $4}')
echo "   Docker build cache: ${BUILD_CACHE:-0B}"

echo ""

# 10. Overall Health Summary
echo -e "${BLUE}[10] OVERALL HEALTH${NC}"
ISSUES=0
[ "$DISK_PCT" -gt 85 ] && ISSUES=$((ISSUES+1))
[ "$RUNNING" -lt "$TOTAL" ] && ISSUES=$((ISSUES+1))
[ "$FAILED" -gt 0 ] && ISSUES=$((ISSUES+1))
[ "$ERROR" -gt 0 ] && ISSUES=$((ISSUES+1))

if [ "$ISSUES" -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
    echo -e "   ${GREEN}✅ OVERALL: HEALTHY${NC}"
else
    echo -e "   ${RED}❌ OVERALL: $ISSUES ISSUE(S) DETECTED${NC}"
fi

echo ""
echo "================================================"
echo -e "${BLUE}✅ System check complete.${NC}"
echo ""
echo "Safe cleanup commands (run manually):"
echo "  # Delete old ReplicaSets (0 replicas) — safe tombstone cleanup"
echo "  kubectl get rs -n $NAMESPACE -o json | jq -r '.items[] | select(.status.replicas==0) | .metadata.name' | xargs -I{} kubectl delete rs {} -n $NAMESPACE --cascade=orphan"
echo "  # Journal vacuum (keep 100MB)"
echo "  sudo journalctl --vacuum-size=100M"
echo "  # Docker build cache"
echo "  docker builder prune -f"
echo "  # k3s unreferenced content blobs"
echo "  sudo /usr/local/bin/k3s ctr -n k8s.io content prune references"
