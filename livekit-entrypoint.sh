#!/bin/sh
# LiveKit Server Entrypoint mit dynamischer IP-Erkennung
# Verhindert IPv6/IPv4-Mismatch in Pion (Egress)
set -e

# Eigene Container-IP ermitteln
NODE_IP=$(hostname -i | awk '{print $1}')
echo "[LiveKit-Server] Detected IP: $NODE_IP"

# LiveKit Server mit dynamischer IP starten (Binary unter /)
exec /livekit-server --config /etc/livekit.yaml --node-ip "$NODE_IP"
