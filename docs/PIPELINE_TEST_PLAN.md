# Pipeline Test Plan — LiveKit Recording Pipeline

**Ziel:** LiveKit Recording Pipeline mit steigender Parallelität testen und Ressourcen-Widerstand prüfen.

**Datum:** 2026-08-06
**Cluster:** Staging (OCI, 158.180.18.110, ARM64)
**Namespace:** `meeting-automation-staging`

---

## 1. Infrastruktur-Status (Verifiziert)

| Komponente | Status | Pods |
|------------|--------|------|
| Backend | ✅ Running | `backend-6956b88574-5tswp`, `backend-6956b88574-t2bvf` |
| LiveKit Server | ✅ Running | hostNetwork, `10.0.0.191` |
| LiveKit Egress | ✅ Running | hostNetwork, `10.0.0.191` |
| Celery Worker (GRATUIT) | ✅ Running | `celery-worker-staging-7d65f46557-6ggx4` |
| Celery Worker (PRO) | ✅ Running | `celery-worker-pro-staging-9bb766b45-6cg27`, `7fh8r` |
| PostgreSQL | ✅ Running | `postgres-staging-0` |
| Redis | ✅ Running | `redis-staging-6cd5fd446c-mr8n8` |
| RabbitMQ | ✅ Running | `rabbitmq-staging-0` |
| MinIO | ✅ Running | `minio-staging-0` |

## 2. Credentials (Verifiziert)

| Credential | Wert |
|------------|------|
| Test User Email | `e2e-tester@staging.meeting.tn` |
| Test User Password | `Password123!` |
| INTERNAL_API_SECRET | `super-secret-automation-key-2026` |
| LIVEKIT_API_KEY | `meeting-api-key` |
| LIVEKIT_API_SECRET | `meeting-api-secret-2026-minimum-32-chars!` |
| DB URL | `postgresql+asyncpg://meeting_user:meeting_password@postgres-staging.meeting-automation-staging.svc.cluster.local:5432/meeting_db_staging` |
| Redis URL | `redis://:redis_password@redis-staging.meeting-automation-staging.svc.cluster.local:6379/0` |
| Celery Broker | `amqp://rabbit_user:rabbit_password@rabbitmq-staging.meeting-automation-staging.svc.cluster.local:5672//` |
| S3 Endpoint | `http://minio-staging:9000` |
| LiveKit URL | `ws://livekit-server-staging:7880` |

## 3. API Endpoints

| Endpoint | Methode | Auth | Zweck |
|----------|---------|------|-------|
| `/api/v1/auth/login` | POST | OAuth2 Form | JWT Token |
| `/api/v1/meetings/` | POST | Bearer JWT | Meeting erstellen |
| `/api/v1/meetings/{id}/livekit/token` | POST | Bearer JWT | LiveKit Token |
| `/api/v1/meetings/{id}/livekit/start-recording` | POST | Bearer JWT | Egress starten |
| `/api/v1/meetings/{id}/livekit/stop-recording` | POST | Bearer JWT | Egress stoppen |
| `/api/v1/livekit/webhooks` | POST | Bearer INTERNAL_API_SECRET | Webhook empfangen |

---

## Phase 1: Einzelner Pipeline-Test

**Ziel:** Pipeline-Grundfunktion verifizieren

### Schritte

1. **Port-Forward einrichten**
   ```bash
   kubectl port-forward -n meeting-automation-staging svc/backend 8080:8000 &
   kubectl port-forward -n meeting-automation-staging svc/meeting-db-rw 5433:5432 &
   kubectl port-forward -n meeting-automation-staging svc/minio-staging 9002:9000 &
   ```

2. **Login → JWT Token**
   ```bash
   curl -c cookies.txt -X POST http://localhost:8080/api/v1/auth/login \
     -d "username=e2e-tester@staging.meeting.tn&password=Password123!"
   ```

3. **Meeting erstellen**
   ```bash
   curl -b cookies.txt -X POST http://localhost:8080/api/v1/meetings/ \
     -H "Content-Type: application/json" \
     -d '{"title":"Pipeline Test 1","start_time":"2026-08-06T10:00:00","end_time":"2026-08-06T11:00:00"}'
   ```

4. **LiveKit Token holen**
   ```bash
   curl -b cookies.txt -X POST http://localhost:8080/api/v1/meetings/{MEETING_ID}/livekit/token
   ```

5. **Recording starten**
   ```bash
   curl -b cookies.txt -X POST http://localhost:8080/api/v1/meetings/{MEETING_ID}/livekit/start-recording
   ```

6. **Recording stoppen (Webhook triggert Pipeline)**
   ```bash
   curl -b cookies.txt -X POST http://localhost:8080/api/v1/meetings/{MEETING_ID}/livekit/stop-recording
   ```

7. **Pipeline-Ergebnisse prüfen**
   - Recording Status in DB prüfen
   - Transkription prüfen
   - PV prüfen
   - Actions prüfen

### Ressourcen-Monitoring

```bash
# Pod Resources
kubectl top pods -n meeting-automation-staging --sort-by=memory
kubectl top pods -n meeting-automation-staging --sort-by=cpu

# Pipeline Logs
kubectl logs -f -n meeting-automation-staging deployment/celery-worker-staging | grep TIMING

# LiveKit Logs
kubectl logs -f -n meeting-automation-staging deployment/livekit-server-staging
kubectl logs -f -n meeting-automation-staging deployment/livekit-egress-staging

# Prometheus Metrics
curl -s 'http://localhost:9090/api/v1/query?query=active_recordings'
curl -s 'http://localhost:9090/api/v1/query?query=pipeline_stage_duration_seconds_bucket'
```

---

## Phase 2: 2 Parallele Pipeline-Tests

**Ziel:** Queue-Verhalten und Celery Worker-Auslastung testen

### Schritte

1. **2 Meetings parallel erstellen**
2. **2 Recordings parallel starten**
3. **2 Webhooks parallel triggern**
4. **Pipeline-Verlauf beobachten**

### Metriken

- Durchsatz (Pipelines/Minute)
- Latenz (P50, P95, P99)
- Celery Queue Depth
- CPU/Memory Auslastung

---

## Phase 3: 5 Parallele Pipeline-Tests

**Ziel:** System-Grenzen finden

### Schritte

1. **5 Meetings parallel erstellen**
2. **5 Recordings parallel starten**
3. **5 Webhooks parallel triggern**
4. **Ressourcen-Engpässe identifizieren**

### Metriken

- Maximale Parallelität
- Fehlerquote
- Ressourcen-Engpässe
- Timeout-Raten

---

## Erfolgskriterien

| Kriterium | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|
| Pipeline abschließen | 100% | ≥90% | ≥80% |
| Keine Fehler | 0 | ≤1 | ≤2 |
| Latenz < 300s | Ja | Ja | Ja |
| CPU < 80% | Ja | Ja | Ja |
| Memory < 80% | Ja | Ja | Ja |

---

## Dokumentation

Ergebnisse werden in `docs/PIPELINE_TEST_RESULTS.md` dokumentiert.
