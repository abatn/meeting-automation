#!/bin/sh
# LiveKit Server Entrypoint mit dynamischer IP-Erkennung
# Verhindert IPv6/IPv4-Mismatch in Pion (Egress)
set -eu

if [ -z "${LIVEKIT_API_KEY:-}" ] || [ -z "${LIVEKIT_API_SECRET:-}" ]; then
  echo "[LiveKit-Server] LIVEKIT_API_KEY and LIVEKIT_API_SECRET are required" >&2
  exit 1
fi

escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[\/&|\\]/\\&/g'
}

# Eigene IPv4 ermitteln; LIVEKIT_NODE_IP kann browser-erreichbar gesetzt werden
# BusyBox hostname unterstützt -I nicht; Fallback auf -i (erste IP)
if [ -n "${LIVEKIT_NODE_IP:-}" ]; then
  NODE_IP="$LIVEKIT_NODE_IP"
else
  NODE_IP=$(hostname -i 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
fi
echo "[LiveKit-Server] Detected IP: $NODE_IP"

LIVEKIT_API_KEY_ESC=$(escape_sed_replacement "$LIVEKIT_API_KEY")
LIVEKIT_API_SECRET_ESC=$(escape_sed_replacement "$LIVEKIT_API_SECRET")

sed \
  -e "s/__LIVEKIT_API_KEY__/${LIVEKIT_API_KEY_ESC}/g" \
  -e "s/__LIVEKIT_API_SECRET__/${LIVEKIT_API_SECRET_ESC}/g" \
  /etc/livekit.yaml > /tmp/livekit.yaml

# LiveKit Server mit dynamischer IP starten (Binary unter /)
exec /livekit-server --config /tmp/livekit.yaml --node-ip "$NODE_IP"
