# Pipeline Simulation Plan — Multi-Tenant Lasttest

**Erstellt:** 2026-08-14
**Cluster:** Staging (OCI, 158.180.18.110, ARM64)
**Node:** 4 CPU Cores, 24 Gi RAM, 183G Disk

---

## 1. Service-Inventar (IST-Zustand)

### 1.1 Deployments (skalierbar)

| Service | Replicas | CPU Req | Mem Req | CPU Lim | Mem Lim | HPA? | Queue/Metrik |
|---------|----------|---------|---------|---------|---------|------|--------------|
| **backend** | 2 | 100m | 256Mi | 500m | 1Gi | ❌ | CPU 70% |
| **celery-worker (GRATUIT)** | 2 | 200m | 1500Mi | 500m | 3Gi | ✅ | CPU 80% (min1,max4) |
| **celery-worker-pro** | 2 | 200m | 2Gi | 1 | 6Gi | ❌ | Queue-Depth |
| **celery-beat** | 1 | 50m | 128Mi | 200m | 512Mi | ❌ | Singleton |
| **frontend** | 1 | 50m | 64Mi | 200m | 128Mi | ❌ | CPU 70% |
| **livekit-server** | 1 | 500m | 512Mi | 1 | 1Gi | ⚠️ Helm (disabled) | CPU 80% (min1,max2) |
| **livekit-egress** | 1 | 200m | 512Mi | 1 | 2Gi | ⚠️ Helm (disabled) | CPU 80% (min1,max2) |
| **n8n** | 1 | 100m | 256Mi | 500m | 1Gi | ❌ | Singleton |
| **onlyoffice** | 1 | 100m | 512Mi | 1 | 2Gi | ❌ | Stateful |
| **redis** | 1 | 100m | 256Mi | 500m | 512Mi | ❌ | In-Memory |

### 1.2 StatefulSets (nicht skalierbar)

| Service | Replicas | CPU Req | Mem Req | Funktion |
|---------|----------|---------|---------|----------|
| **postgres-staging** | 1 | 100m | 256Mi | PostgreSQL Primary |
| **minio-staging** | 1 | 200m | 512Mi | S3 Object Storage |
| **rabbitmq-staging** | 1 | 200m | 512Mi | Message Broker |

### 1.3 Node Ressourcen

| Metrik | Wert | Auslastung |
|--------|------|------------|
| **CPU Cores** | 4 | 42% (1687m/4000m) |
| **Memory** | 24 Gi | 66% (15260Mi) |
| **Disk** | 183G | 79% (145G) |

---

## 2. Pipeline-Flow (Multi-Tenant)

```
Tenant (PRO/GRATUIT)
  │
  ├─ Backend API ──→ PostgreSQL (Read/Write)
  │                   └─ Rate Limiter (Redis)│  ├─ LiveKit Server ──→ WebRTC (stateless, hostNetwork)
  │                      └─ Egress (1 Pod, hostNetwork, autoscaling-ready)
  │
  ├─ MinIO/S3 ──→ Audio Upload/Download
  │
  ├─ Celery Worker (GRATUIT) ──→ Queue: transcription_gratuit
  │   └─ Gladia API (external)
  │   └─ Speaker ID (ONNX)
  │   └─ Mistral API (external, Semaphore=2)
  │   └─ PostgreSQL (Write)
  │
  └─ Celery Worker (PRO) ──→ Queue: transcription_pro
      └─ Gladia API (external)
      └─ Speaker ID (ONNX)
      └─ Sentinel LLM (Qwen 1.5B, Semaphore=2)
      └─ Mistral API (external, Semaphore=2)
      └─ PostgreSQL (Write)
```

---

## 3. Simulations-Szenarien

### Szenario 1: 1 Tenant (Baseline)

| Metrik | Erwartung |
|--------|-----------|
| Pipelines gleichzeitig | 1 |
| CPU Peak | ~30% |
| Memory Peak | ~60% |
| Pipeline-Dauer | ~8s (Sine Wave) |

**Ziel:** Baseline für Vergleich definieren.

### Szenario 2: 3 Tenants (PRO + GRATUIT + ENTREPRISE)

| Metrik | Erwartung |
|--------|-----------|
| Pipelines gleichzeitig | 3 (sequenziell gestartet, parallel verarbeitet) |
| Recordings gleichzeitig | 1 (Egress 1 Pod) |
| CPU Peak | ~70% |
| Memory Peak | ~80% |
| Pipeline-Dauer | ~3min pro Pipeline |
| LiveKit Server | 3 Rooms gleichzeitig (stateless, kein Limit) |
| LiveKit Egress | 3 Recordings sequenziell (1 Pod, autoscaling-ready) |

**Ziel:** Multi-Tenant Isolation beweisen.

**LiveKit-Verhalten:** Server handhabt 3 Rooms parallel (stateless, CPU-begrenzt). Egress verarbeitet 3 Recordings nacheinander. Bei aktiviertem Autoscaling (max2) könnten 2 Recordings parallel laufen — aber nur bei Multi-Node.

### Szenario 3: 5 Tenants (Lasttest)

| Metrik | Erwartung |
|--------|-----------|
| Pipelines gleichzeitig | 5 |
| Recordings gleichzeitig | 1 (Egress 1 Pod) |
| CPU Peak | ~95% (Overcommit) |
| Memory Peak | ~90% |
| Pipeline-Dauer | ~5min pro Pipeline |
| LiveKit Server | 5 Rooms (CPU steigt, autoscaling-ready) |
| LiveKit Egress | 5 Recordings sequenziell (autoscaling-ready) |

**Ziel:** System-Grenzen finden.

**LiveKit-Verhalten:** Server kann 5 Rooms handhaben (stateless, CPU-begrenzt). Egress wird zum Flaschenhals — 5 Recordings nacheinander = lange Gesamtdauer. **Lösung:** Helm autoscaling.enabled: true (bei Multi-Node).

### Szenario 4: Burst (10 Tenants in 1 Minute)

| Metrik | Erwartung |
|--------|-----------|
| Pipelines gleichzeitig | 10 |
| Recordings gleichzeitig | 1 (Egress 1 Pod) |
| CPU Peak | 100% (Throttling) |
| Memory Peak | ~95% |
| Pipeline-Dauer | ~10min pro Pipeline |
| LiveKit Server | 10 Rooms (CPU 100%, autoscaling-ready) |
| LiveKit Egress | 10 Recordings sequenziell (autoscaling-ready) |

**Ziel:** Under-Provisioning identifizieren.

**LiveKit-Verhalten:** Server bei 10 Rooms am Limit. Egress: 10 Recordings nacheinander = ~30min Gesamtdauer. **Lösung:** Helm autoscaling.enabled: true + maxReplicas: 3 + Multi-Node Cluster.

---

## 4. Messpunkte pro Service

### 4.1 Backend

| Metrik | Quelle | Trigger für HPA |
|--------|--------|-----------------|
| CPU Usage | `kubectl top pod` | > 70% |
| Request Rate | Prometheus `http_requests_total` | > 100 req/s |
| Response Latency | Prometheus `http_request_duration_seconds` | P95 > 500ms |
| Error Rate | Prometheus `http_requests_total{status=~"5.."}` | > 1% |

### 4.2 Celery Workers (GRATUIT)

| Metrik | Quelle | Trigger für HPA |
|--------|--------|-----------------|
| Queue Depth | RabbitMQ `rabbitmq_queue_messages` | > 5 |
| CPU Usage | `kubectl top pod` | > 80% |
| Memory Usage | `kubectl top pod` | > 80% |
| Task Duration | Celery `task_time` | P95 > 300s |
| Worker Active | Celery `celery_worker_active` | = replicas |

### 4.3 Celery Workers (PRO)

| Metrik | Quelle | Trigger für HPA |
|--------|--------|-----------------|
| Queue Depth | RabbitMQ `rabbitmq_queue_messages` | > 3 |
| CPU Usage | `kubectl top pod` | > 70% |
| Memory Usage | `kubectl top pod` | > 70% (Sentinel LLM!) |
| Task Duration | Celery `task_time` | P95 > 600s |
| Sentinel Memory | `container_memory_usage_bytes` | > 4Gi |

### 4.4 LiveKit Server

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Active Rooms | LiveKit API `list_rooms` | > 10 |
| CPU Usage | `kubectl top pod` | > 80% (Helm autoscaling Trigger) |
| Memory Usage | `kubectl top pod` | > 80% |
| WebRTC Connections | LiveKit `room_participants` | > 50 |
| Pods | `kubectl get pods` | > 1 (bei Autoscaling) |

**Helm-Autoscaling:** `autoscaling.enabled: false`, `minReplicas: 1`, `maxReplicas: 2`, `targetCPU: 80%`

**Hinweis:** Bei hostNetwork + Single-Node bringt Autoscaling nichts (2 Pods auf 1 Node = gleicher CPU). Erst sinnvoll bei Multi-Node.

### 4.5 LiveKit Egress

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Active Recordings | LiveKit API `list_egress` | > 0 (aktuell 1 Pod) |
| CPU Usage | `kubectl top pod` | > 80% (Helm autoscaling Trigger) |
| Memory Usage | `kubectl top pod` | > 80% |
| Egress Errors | Egress logs | > 0 |
| Pods | `kubectl get pods` | > 1 (bei Autoscaling) |

**Helm-Autoscaling:** `autoscaling.enabled: false`, `minReplicas: 1`, `maxReplicas: 2`

**Hinweis:** Mehrere Egress-Pods ermöglichen parallele Recordings. Aber: hostNetwork = jeder Pod braucht eigenen Port (50000-60000 Range). Bei Single-Node: nur 1 Egress sinnvoll.

### 4.6 PostgreSQL

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Active Connections | `pg_stat_activity` | > 50 |
| Query Duration | `pg_stat_statements` | P95 > 100ms |
| Cache Hit Ratio | `pg_stat_database` | < 95% |
| Replication Lag | CNPG metrics | > 1s |
| Disk Usage | `pg_database_size` | > 80% |

### 4.7 Redis

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Memory Usage | `redis-cli info memory` | > 80% |
| Connected Clients | `redis-cli info clients` | > 100 |
| Hit Rate | `redis-cli info stats` | < 80% |
| Evictions | `redis-cli info stats` | > 0 |

### 4.8 RabbitMQ

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Queue Depth | `rabbitmqctl list_queues` | > 10 |
| Consumers | `rabbitmqctl list_queues` | = 0 (kein Consumer!) |
| Memory Usage | `rabbitmqctl status` | > 80% |
| Disk Usage | `rabbitmqctl status` | > 80% |

### 4.9 MinIO

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Disk Usage | `minio admin info` | > 80% |
| Concurrent Connections | MinIO metrics | > 50 |
| Upload/Download Rate | MinIO metrics | > 100MB/s |

### 4.10 External APIs

| Metrik | Quelle | Trigger |
|--------|--------|---------|
| Gladia Response Time | HTTP metrics | P95 > 30s |
| Gladia Error Rate | HTTP metrics | > 5% |
| Mistral Response Time | HTTP metrics | P95 > 30s |
| Mistral Error Rate | HTTP metrics | > 5% |
| Mistral 429 Rate | HTTP metrics | > 0 |

---

## 5. Simulations-Befehle

### 5.1 Cluster-State vor Test

```bash
# Node Ressourcen
kubectl top nodes

# Alle Pods
kubectl top pods -n meeting-automation-staging --sort-by=cpu

# RabbitMQ Queues
kubectl exec -n meeting-automation-staging rabbitmq-staging-0 -- \
  rabbitmqctl list_queues name messages consumers

# Disk
df -h /
```

### 5.2 Tenants erstellen

```bash
# 3 Tenants: GRATUIT, PRO, ENTREPRISE
for PLAN in GRATUIT PRO ENTREPRISE; do
  curl -X POST http://localhost:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"test-${PLAN,,}@staging.tn\",\"password\":\"Test123!\",\"full_name\":\"${PLAN} Tester\",\"company_name\":\"${PLAN} Test\",\"plan\":\"${PLAN}\"}"
done
```

### 5.3 Meetings parallel erstellen

```bash
# 3 Meetings parallel (in Background)
for i in 1 2 3; do
  curl -s -X POST http://localhost:8000/api/v1/meetings/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"Sim-Test-$i\",\"start_time\":\"2026-08-14T15:00:00\",\"end_time\":\"2026-08-14T16:00:00\"}" &
done
wait
```

### 5.4 Recordings starten (sequenziell wegen Egress)

```bash
# Recording starten (1 auf einmal — Egress single-threaded)
for MID in $M1 $M2 $M3; do
  curl -s -X POST "http://localhost:8000/api/v1/meetings/$MID/livekit/start-recording" \
    -H "Authorization: Bearer $TOKEN"
  sleep 2
  # Audio senden
  lk room join --url "wss://staging.meeting-automation.com" \
    --api-key "meeting-api-key" \
    --api-secret "meeting-api-secret-2026-minimum-32-chars!" \
    --publish /tmp/test_audio.ogg \
    --exit-after-publish "$MID"
  sleep 1
  # Recording stoppen
  curl -s -X POST "http://localhost:8000/api/v1/meetings/$MID/livekit/stop-recording" \
    -H "Authorization: Bearer $TOKEN"
done
```

### 5.5 Pipeline live verfolgen

```bash
# TIMING Logs
kubectl logs -f -n meeting-automation-staging -l app=celery-worker-pro-staging | grep TIMING

# RabbitMQ Queue Depth
watch -n 5 "kubectl exec -n meeting-automation-staging rabbitmq-staging-0 -- rabbitmqctl list_queues name messages consumers"

# Pod Resources
watch -n 5 "kubectl top pods -n meeting-automation-staging --sort-by=cpu"
```

---

## 6. Erwartete Ergebnisse

### Szenario 1 (1 Tenant)

| Service | CPU | Memory | Status |
|---------|-----|--------|--------|
| backend | 5% | 200Mi | ✅ Idle |
| celery-worker (GRATUIT) | 10% | 400Mi | ✅ Idle |
| celery-worker-pro | 20% | 500Mi | ✅ Idle |
| livekit-server | 5% | 50Mi | ✅ Idle |
| livekit-egress | 10% | 20Mi | ✅ Recording |
| postgres | 5% | 200Mi | ✅ Idle |
| redis | 5% | 50Mi | ✅ Idle |
| rabbitmq | 10% | 100Mi | ✅ Idle |
| minio | 5% | 100Mi | ✅ Idle |

### Szenario 2 (3 Tenants)

| Service | CPU | Memory | Status |
|---------|-----|--------|--------|
| backend | 15% | 400Mi | ✅ OK |
| celery-worker (GRATUIT) | 30% | 800Mi | ✅ OK |
| celery-worker-pro | 60% | 1.5Gi | ⚠️ Sentinel loaded |
| livekit-server | 15% | 150Mi | ✅ OK |
| livekit-egress | 30% | 60Mi | ⚠️ Single-threaded |
| postgres | 20% | 400Mi | ✅ OK |
| redis | 10% | 100Mi | ✅ OK |
| rabbitmq | 15% | 200Mi | ✅ OK |
| minio | 10% | 200Mi | ✅ OK |

### Szenario 3 (5 Tenants)

| Service | CPU | Memory | Status |
|---------|-----|--------|--------|
| backend | 25% | 600Mi | ✅ OK |
| celery-worker (GRATUIT) | 50% | 1.5Gi | ⚠️ Near limit |
| celery-worker-pro | 90% | 4Gi | ❌ Near OOM |
| livekit-server | 25% | 250Mi | ⚠️ High |
| livekit-egress | 50% | 100Mi | ❌ Bottleneck |
| postgres | 40% | 800Mi | ⚠️ High |
| redis | 20% | 200Mi | ✅ OK |
| rabbitmq | 25% | 400Mi | ✅ OK |
| minio | 15% | 400Mi | ✅ OK |

### Szenario 4 (10 Tenants — Burst)

| Service | CPU | Memory | Status |
|---------|-----|--------|--------|
| backend | 50% | 1Gi | ⚠️ Needs scaling |
| celery-worker (GRATUIT) | 100% | 3Gi | ❌ OOM Risk |
| celery-worker-pro | 100% | 6Gi | ❌ OOM Kill |
| livekit-server | 50% | 500Mi | ❌ Overloaded |
| livekit-egress | 100% | 2Gi | ❌ Single-threaded |
| postgres | 80% | 1.5Gi | ❌ Connection limit |
| redis | 40% | 400Mi | ⚠️ High |
| rabbitmq | 50% | 800Mi | ⚠️ High |
| minio | 30% | 800Mi | ✅ OK |

---

## 7. HPA-Vorschläge (nach Simulation)

### 7.1 Für jeden Service

| Service | Aktuelle HPA | Helm-Autoscaling | Vorschlag | Metrik | Min | Max |
|---------|-------------|------------------|-----------|--------|-----|-----|
| **backend** | ❌ Keine | ❌ Kein Helm | ✅ CPU 70% | CPU | 2 | 6 |
| **celery-worker (GRATUIT)** | ✅ CPU 80% | — | Beibehalten | CPU | 1 | 4 |
| **celery-worker-pro** | ❌ Keine | — | ✅ Queue-Depth > 3 | Custom | 1 | 4 |
| **frontend** | ❌ Keine | ❌ Kein Helm | ✅ CPU 70% | CPU | 1 | 3 |
| **livekit-server** | ❌ Keine | ✅ `enabled: false` | ⚠️ Aktivieren bei Multi-Node | CPU 80% | 1 | 2 |
| **livekit-egress** | ❌ Keine | ✅ `enabled: false` | ⚠️ Aktivieren bei Multi-Node | CPU 80% | 1 | 2 |

**LiveKit-Hinweis:** Beide haben Helm-Autoscaling konfiguriert (min1, max2, CPU 80%). Bei Single-Node (Staging/Production) ist es deaktiviert — erst sinnvoll bei Multi-Node (2. Node hinzufügen).

### 7.2 Custom Metrics (benötigt Prometheus Adapter)

| Metrik | Quelle | HPA Ziel |
|--------|--------|----------|
| `rabbitmq_queue_messages{queue="transcription_pro"}` | RabbitMQ Prometheus | PRO Workers |
| `rabbitmq_queue_messages{queue="transcription_gratuit"}` | RabbitMQ Prometheus | GRATUIT Workers |
| `http_requests_total{route="/api/v1/meetings"}` | Backend Metrics | Backend |
| `active_recordings` | LiveKit Metrics | Egress |

### 7.3 Infrastruktur-Änderungen

| Änderung | Komplexität | Priorität |
|----------|-------------|-----------|
| Prometheus Adapter installieren | Mittel | P1 |
| RabbitMQ Prometheus Plugin aktivieren | Niedrig | P1 |
| Custom Metrics API bereitstellen | Hoch | P2 |
| KEDA installieren (optional) | Hoch | P3 |

---

## 8. Messprotokoll

### 8.1 Vor dem Test

```bash
# 1. Cluster-State dokumentieren
kubectl top nodes > /tmp/before-test.txt
kubectl top pods -n meeting-automation-staging >> /tmp/before-test.txt
kubectl exec -n meeting-automation-staging rabbitmq-staging-0 -- \
  rabbitmqctl list_queues name messages consumers >> /tmp/before-test.txt

# 2. Prometheus Snapshot
curl -s 'http://localhost:9090/api/v1/query?query=container_cpu_usage_seconds_total' > /tmp/prom-before.json

# 3. Timestamp
echo "Test started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)" > /tmp/test-timeline.txt
```

### 8.2 Während des Tests

```bash
# Alle 30s messen
watch -n 30 "echo '=== $(date -u +%H:%M:%S) ===' && kubectl top pods -n meeting-automation-staging --sort-by=cpu && echo && kubectl exec -n meeting-automation-staging rabbitmq-staging-0 -- rabbitmqctl list_queues name messages consumers"
```

### 8.3 Nach dem Test

```bash
# 1. Cluster-State dokumentieren
kubectl top nodes > /tmp/after-test.txt
kubectl top pods -n meeting-automation-staging >> /tmp/after-test.txt

# 2. Pipeline-Ergebnisse
kubectl exec -n meeting-automation-staging deployment/backend -- python3 -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.recording import Recording
from sqlalchemy import select, desc
async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).order_by(desc(Recording.created_at)).limit(10))
        for r in result.scalars().all():
            print(f'{str(r.meeting_id)[:8]} | {r.status} | size={r.file_size}')
asyncio.run(check())
"

# 3. Fehler-Logs
kubectl logs -n meeting-automation-staging -l app=celery-worker-pro-staging --since=30m | grep -iE "error|exception|timeout" | tail -20
```

---

## 9. Erfolgskriterien

| Kriterium | Szenario 1 | Szenario 2 | Szenario 3 | Szenario 4 |
|-----------|------------|------------|------------|------------|
| Pipeline abschließen | 100% | 100% | ≥90% | ≥80% |
| Keine OOM Kills | ✅ | ✅ | ✅ | ⚠️ |
| CPU < 80% | ✅ | ✅ | ⚠️ | ❌ |
| Memory < 80% | ✅ | ✅ | ⚠️ | ❌ |
| Keine 429 Errors | ✅ | ✅ | ⚠️ | ❌ |
| Pipeline-Dauer < 300s | ✅ | ✅ | ⚠️ | ❌ |

---

## 10. Nächste Schritte

1. **Szenario 1 ausführen** (Baseline)
2. **Szenario 2 ausführen** (Multi-Tenant)
3. **Ergebnisse dokumentieren** (PIPELINE_TEST_RESULTS.md)
4. **HPA implementieren** (nach Simulation)
5. **Prometheus Adapter installieren** (für Custom Metrics)
6. **Production Test** (nach Staging-Validierung)
