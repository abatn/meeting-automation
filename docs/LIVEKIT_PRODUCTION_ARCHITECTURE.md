# LiveKit Production Architecture

> **Aktualisiert**: 2026-06-24 | k3s Migration abgeschlossen (Phase 33)

## Problem Statement

LiveKit WebRTC requires direct UDP access for real-time media traffic. Kind clusters (Kubernetes in Docker) have multiple NAT layers that block UDP traffic, making them fundamentally incompatible with LiveKit WebRTC.

### Why Other Services Work in Kind

| Service | Protocol | Works in Kind? |
|---------|----------|----------------|
| Redis | TCP only | ✅ Yes |
| MinIO | TCP only | ✅ Yes |
| PostgreSQL | TCP only | ✅ Yes |
| RabbitMQ | TCP only | ✅ Yes |
| **LiveKit** | TCP + **UDP** | ❌ **No** |

**Key Insight**: TCP ports are forwarded by Kind, but UDP ports are blocked by NAT layers.

### LiveKit Port Requirements

| Port | Protocol | Purpose |
|------|----------|---------|
| 7880 | TCP | WebSocket Signaling |
| 7881 | TCP | ICE/TCP (fallback) |
| 50000-60000 | **UDP** | ICE/UDP (media per participant) |
| 3478 | UDP | TURN/UDP (optional) |

Reference: https://docs.livekit.io/transport/self-hosting/kubernetes/

> "LiveKit does not support deployment to serverless and/or **private clusters**. Private clusters have additional layers of NAT that make it unsuitable for WebRTC traffic."

---

## Architecture Overview

### Staging (Current: k3s Cluster) ✅

```
┌─────────────────────────────────────────────────────────────┐
│  OCI VM (158.180.18.110, 4 CPU, 22GB RAM, ARM64)           │
│  k3s v1.35.5+k3s1                                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  meeting-automation-staging namespace                │   │
│  │                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │   │
│  │  │ LiveKit      │ │ Backend      │ │ Frontend    │ │   │
│  │  │ (hostNetwork)│ │ (2 replicas) │ │ (NodePort)  │ │   │
│  │  │ :7880 TCP    │ │ :8000        │ │ :31362      │ │   │
│  │  │ :7881 TCP    │ │              │ │             │ │   │
│  │  │ UDP ✓        │ │              │ │             │ │   │
│  │  └──────────────┘ └──────────────┘ └─────────────┘ │   │
│  │                                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │   │
│  │  │ Egress       │ │ PostgreSQL   │ │ MinIO       │ │   │
│  │  │ (hostNetwork)│ │ (StatefulSet)│ │ (StatefulSet│ │   │
│  │  │ S3: minio    │ │ :5432        │ │ :9000       │ │   │
│  │  └──────────────┘ └──────────────┘ └─────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Connection Flow (k3s)**:
1. Browser → `ws://158.180.18.110:7880` (LiveKit signaling via hostNetwork)
2. Browser ← LiveKit returns ICE candidates (UDP ports)
3. Browser ↔ LiveKit (UDP media stream via hostNetwork)
4. Backend → `ws://livekit-config-staging:7880` (internal K8s DNS)
5. Egress → `minio-staging:9000` (internal K8s DNS)

### Production (Cloud-VM)

```
┌─────────────────────────────────────────────────────────────┐
│  Cloud-VM (AWS EC2 / GCP Compute / etc.)                   │
│  Public IP: 1.2.3.4                                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Docker Compose                                     │   │
│  │                                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ LiveKit  │ │ Backend  │ │ Frontend │            │   │
│  │  │ (host)   │ │ (bridge) │ │ (bridge) │            │   │
│  │  │ :7880    │ │ :8000    │ │ :3000    │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  │                                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ Postgres │ │ Redis    │ │ MinIO    │            │   │
│  │  │ :5432    │ │ :6379    │ │ :9000    │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Connection Flow**:
1. Browser → `wss://livekit.yourdomain.com` (LiveKit signaling)
2. Browser ← LiveKit returns ICE candidates (UDP ports)
3. Browser ↔ LiveKit (UDP media stream)
4. Backend → `ws://localhost:7880` (internal API)

---

## Implementation

### 1. Docker Compose for LiveKit on Host

```yaml
# docker-compose.livekit.yml (NEVER EXISTED)
version: '3.8'

services:
  livekit-server:
    image: livekit/livekit-server:latest
    container_name: livekit-server
    network_mode: host
    volumes:
      - ./livekit-server.yaml:/etc/livekit.yaml
    command: --config /etc/livekit.yaml --bind 0.0.0.0
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  livekit-redis:
    image: redis:7-alpine
    container_name: livekit-redis
    ports:
      - "6380:6379"
    volumes:
      - livekit-redis-data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  livekit-redis-data:
```

### 2. LiveKit Server Configuration

```yaml
# livekit-host.yaml (Staging - Kind)
port: 7880
log_level: info

rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
  force_tcp: false

redis:
  address: localhost:6380

keys:
  your_api_key: your_api_secret

turn:
  enabled: true
  udp_port: 3478
```

### 3. Backend ConfigMap Update

**Staging (Kind):** Use DNS name via `hostAliases`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
  namespace: meeting-automation-staging
data:
  LIVEKIT_URL: "ws://livekit-host.local:7880"
  LIVEKIT_PUBLIC_URL: "ws://158.180.18.110:7880"
```

**Production (Cloud-VM):** Use localhost (LiveKit runs on same host)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  LIVEKIT_URL: "ws://localhost:7880"
  LIVEKIT_PUBLIC_URL: "wss://livekit.yourdomain.com"
```

### 4. Disable Kind LiveKit Deployment

```bash
# Scale down to 0 replicas (keep for reference)
kubectl scale deployment/livekit-server --replicas=0 -n meeting-automation-staging
kubectl scale deployment/livekit-egress --replicas=0 -n meeting-automation-staging
```

### 5. Kind Staging: hostAliases Configuration

For Kind clusters, use `hostAliases` to map DNS names to the Docker gateway IP:

```yaml
# Backend Deployment patch
spec:
  template:
    spec:
      hostAliases:
        - ip: "<docker-gateway-ip>"  # Detected by: docker network inspect kind
          hostnames:
            - "livekit-host.local"
```

**Setup script auto-detection:**
```bash
DOCKER_GATEWAY=$(docker network inspect kind -f '{{range .IPAM.Config}}{{if eq .Subnet "172.18.0.0/16"}}{{.Gateway}}{{end}}{{end}}')
kubectl patch deployment backend -n meeting-automation-staging --type=json \
    -p "[{\"op\":\"add\",\"path\":\"/spec/template/spec/hostAliases\",\"value\":[{\"ip\":\"$DOCKER_GATEWAY\",\"hostnames\":[\"livekit-host.local\"]}]}]"
```

**Why this is professional:**
- Application code uses only DNS names (no hardcoded IPs)
- Infrastructure config (hostAliases) is per-environment
- Setup script detects IP automatically
- Production uses real DNS, no hostAliases needed

---

## Testing Checklist

### Staging Tests

- [ ] LiveKit server running on host: `curl http://localhost:7880`
- [ ] Backend connects to LiveKit: `curl http://localhost:8000/health`
- [ ] Browser WebSocket connection: Open DevTools → Network → WS
- [ ] WebRTC ICE candidates: Check browser console for UDP candidates
- [ ] Audio/Video stream: Join room, verify media flow
- [ ] Recording: Start recording, verify file in MinIO

### Production Tests

- [ ] SSL/TLS: `wss://livekit.yourdomain.com` works
- [ ] Firewall: UDP ports 50000-60000 open
- [ ] Load balancer: TCP 7880 forwarded correctly
- [ ] TURN/TLS: Port 443 or 5349 accessible
- [ ] Monitoring: Prometheus metrics available

---

## Production Deployment Guide

### Prerequisites

1. Cloud VM (AWS EC2 t3.medium or similar)
2. Docker + Docker Compose installed
3. Domain name with DNS configured
4. SSL certificate (Let's Encrypt or AWS ACM)
5. Firewall rules:
   - TCP 80, 443 (HTTP/HTTPS)
   - TCP 7880 (LiveKit signaling)
   - TCP 7881 (ICE/TCP)
   - UDP 50000-60000 (ICE/UDP)
   - UDP 3478 (TURN/UDP)

### Deployment Steps

```bash
# 1. Clone repository
git clone https://github.com/your-org/meeting-automation.git
cd meeting-automation

# 2. Configure environment
cp .env.example .env
# Edit .env with production values

# 3. Start all services
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify LiveKit
curl http://localhost:7880
# Should return "LiveKit Server"

# 5. Check logs
docker-compose logs -f livekit-server
```

### SSL/TLS Configuration

```yaml
# nginx.conf (production)
server {
    listen 443 ssl;
    server_name livekit.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/livekit.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/livekit.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:7880;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| WebSocket connection fails | Port 7880 blocked | Check firewall rules |
| ICE candidates not received | UDP ports blocked | Open UDP 50000-60000 |
| No audio/video | NAT traversal failed | Enable TURN server |
| Connection timeout | SSL mismatch | Verify certificate |

### Debug Commands

```bash
# Check LiveKit server
curl http://localhost:7880

# Check UDP ports
netstat -uln | grep -E "7880|7881|50000-60000"

# Check firewall
sudo ufw status
sudo iptables -L -n | grep -E "7880|7881|50000-60000"

# LiveKit logs
docker logs livekit-server

# Test WebRTC connection
# Open browser console and check for:
# - "WebSocket connected"
# - "ICE candidates received"
# - "Media stream established"
```

---

## Cost Comparison

| Setup | Monthly Cost | Complexity | Best For |
|-------|--------------|------------|----------|
| Kind + LiveKit on Host | 0€ | Medium | Staging |
| Cloud-VM + Docker Compose | 20-50€ | Low | Production (small) |
| Cloud-Kubernetes (GKE/EKS) | 100-300€ | High | Production (large) |
| LiveKit Cloud (managed) | 50-200€ | Very Low | Quick start |

---

## References

- LiveKit Documentation: https://docs.livekit.io/transport/self-hosting/kubernetes/
- LiveKit Helm Chart: https://github.com/livekit/livekit-helm
- LiveKit Docker: https://docs.livekit.io/transport/self-hosting/deployment/
- WebRTC Port Requirements: https://docs.livekit.io/transport/self-hosting/ports-firewall/

---

*Last updated: 2026-06-24*
*Author: Meeting Automation Team*