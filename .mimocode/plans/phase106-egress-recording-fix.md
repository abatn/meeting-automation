# Phase 106: LiveKit Egress Recording Fix — CPU + Image Pinning

## Status: 📋 GEPLANT — Root Cause 100% bestätigt via Logs

## Root Cause (100% bestätigt via Logs)
- Recording hat am 26. Juni 2026 FUNKTIONIERT (8 completed recordings in DB)
- Gleiche Config: CPU limit 1, hostNetwork, ConfigMap unverändert
- Was sich geändert hat: `livekit/egress:latest` Image hat neue Version (1.13.0) gepullt
- Neue Version: `minimumCpu: 2, available: 1` → Egress registriert sich NICHT für `roomComposite` in PSRPC
- PSRPC-Topic bleibt leer → LiveKit Server gibt 503 nach 23s Timeout

## Beweise
1. DB: 8 completed recordings am 26. Juni (Egress IDs vorhanden, Status: completed)
2. Egress ConfigMap: unverändert seit Phase 33 (cpu_cost.room_composite_cpu_cost: 1.5)
3. Egress Deployment: CPU limit war IMMER 1 (seit Phase 33)
4. Egress Startup Log (heute): `ERROR not enough cpu for some egress types, minimumCpu: 2, available: 1`
5. Redis KEYS: 0 PSRPC-Keys → Egress registriert sich nicht
6. LiveKit Server: `"topic": [""]` → `no response from servers` nach 23s → 503

## Änderungen

| # | Ressource | Änderung | Begründung |
|---|-----------|----------|------------|
| 1 | `livekit-egress-staging` Deployment | CPU limit `1` → `2` | minimumCpu=2 für composite recording (Egress 1.13.0) |
| 2 | `livekit-egress-staging` Deployment | Image `latest` → `1.13.0` | Pinning verhindert zukünftige Breaks |
| 3 | `livekit-server-staging` Deployment | Image `latest` → pinned | Konsistenz + Safety |
| 4 | `infrastructure/kubernetes/staging/livekit-egress-deployment.yaml` | Image Pinning | Git als Quelle |
| 5 | `.loop.md` Phase 106 | Dokumentiert | |
| 6 | `docs/ISO27001.md` | Egress CPU Update | Compliance |

## Resource Impact
- Node 1 (4 vCPU): CPU limits 6000m → 7000m (175%, OK)
- Kein Memory-Change (2Gi reicht)
- Kein Node-Wechsel (bleibt Node 1 für hostNetwork + OCI LiveKit Ports)

## Verification
1. Egress Startup-Log: kein `not enough cpu` Error
2. Redis KEYS: PSRPC-Keys vorhanden
3. LiveKit Server: topic nicht mehr leer
4. Recording: StartRoomCompositeEgress → 200 OK (nicht 503)
5. User: Start/Stop Recording funktioniert
