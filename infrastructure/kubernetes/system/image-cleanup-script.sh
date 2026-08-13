#!/bin/bash
# Image Cleanup Script for k3s
# Run weekly via systemd timer or cron
# Location: /usr/local/bin/image-cleanup.sh

set -e

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="/var/log/image-cleanup.log"

echo "[$TIMESTAMP] === Containerd Image Cleanup ===" | tee -a "$LOG_FILE"

# --- Phase 1: Get disk usage before ---
DISK_BEFORE=$(df -h / | tail -1 | awk '{print $5}')
echo "[$TIMESTAMP] Disk before: $DISK_BEFORE" | tee -a "$LOG_FILE"

# --- Phase 2: Prune unused images ---
echo "[$TIMESTAMP] Phase 2: Pruning unused containerd images..." | tee -a "$LOG_FILE"

# Use k3s ctr to prune images
if command -v k3s &> /dev/null; then
    echo "[$TIMESTAMP] Using k3s ctr" | tee -a "$LOG_FILE"
    k3s ctr images prune --all 2>&1 | tee -a "$LOG_FILE"
elif command -v ctr &> /dev/null; then
    echo "[$TIMESTAMP] Using ctr" | tee -a "$LOG_FILE"
    ctr images prune --all 2>&1 | tee -a "$LOG_FILE"
else
    echo "[$TIMESTAMP] ERROR: Neither k3s nor ctr found" | tee -a "$LOG_FILE"
    exit 1
fi

# --- Phase 3: Get disk usage after ---
DISK_AFTER=$(df -h / | tail -1 | awk '{print $5}')
echo "[$TIMESTAMP] Disk after: $DISK_AFTER" | tee -a "$LOG_FILE"

# --- Phase 4: Summary ---
echo "[$TIMESTAMP] === Summary ===" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] Disk before: $DISK_BEFORE" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] Disk after: $DISK_AFTER" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] === Image cleanup complete ===" | tee -a "$LOG_FILE"

# Rotate log if too large (>1MB)
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt 1048576 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    echo "[$TIMESTAMP] Log rotated" | tee -a "$LOG_FILE"
fi
