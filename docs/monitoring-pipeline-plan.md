# Pipeline Monitoring Plan — Meeting Automation

## Übersicht

Dieser Plan definiert alle Metriken, Dashboards und Alerts für die Meeting Automation Pipeline.

## 1. Pipeline-Metriken (Business-Level)

### Recording-Pipeline
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `recording_uploads_total` | Backend /metrics | — |
| `recording_upload_duration_seconds` | Backend /metrics | > 30s |
| `recording_processing_duration_seconds` | Celery Task | > 90s (Ziel) |
| `recording_failures_total` | Celery Task | > 5/Min |

### Transcription-Pipeline
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `gladia_api_latency_seconds` | transcription_tasks | > 30s |
| `mistral_pv_latency_seconds` | pv_service | > 30s |
| `speaker_id_duration_seconds` | transcription_tasks | > 30s |
| `pipeline_total_duration_seconds` | transcription_tasks | > 90s (Ziel) |
| `pipeline_failures_total` | Celery Task | > 2/Min |

### S3/MinIO
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `s3_upload_duration_seconds` | recording_service | > 10s |
| `s3_download_duration_seconds` | transcription_tasks | > 10s |
| `s3_errors_total` | boto3 exceptions | > 1/Min |
| `minio_storage_used_bytes` | MinIO /minio/v2/metrics | > 80% PVC |

## 2. Infrastructure-Metriken

### Kubernetes
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `kube_pod_status_ready` | node-exporter | Pod nicht Ready > 5Min |
| `kube_pod_container_resource_requests` | node-exporter | — |
| `kube_node_status_condition` | node-exporter | NotReady > 5Min |
| `kube_persistentvolumeclaim_status_phase` | node-exporter | Pending > 10Min |

### PostgreSQL (CNPG)
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `pg_stat_activity_count` | postgres-exporter | > 180 (max_connections=200) |
| `pg_stat_replication_lag_seconds` | CNPG Operator | > 30s |
| `pg_database_size_bytes` | postgres-exporter | > 8GB (10Gi PVC) |
| `pg_stat_database_xact_commit` | postgres-exporter | — |

### Redis
| Metrik | Quelle | Alert |
|--------|--------|-------|
| `redis_memory_used_bytes` | redis-exporter | > 100MB (128Mi Limit) |
| `redis_connected_clients` | redis-exporter | > 50 |
| `redis_keyspace_hits_ratio` | redis-exporter | < 80% |

## 3. Celery-Metriken

| Metrik | Quelle | Alert |
|--------|--------|-------|
| `celery_queue_length` | RabbitMQ Management | > 100 Tasks |
| `celery_task_success_rate` | Celery Flower / custom | < 95% |
| `celery_worker_memory_bytes` | kubectl top | > 3.5Gi (Limit 4Gi) |
| `celery_task_duration_seconds` | Celery Beat | > 120s |
| `celery_worker_restarts_total` | k3s events | > 3/Stunde |

## 4. Alerting Rules

### Critical (PagerDuty/Slack)
```yaml
groups:
  - name: meeting-automation-critical
    rules:
    - alert: PodCrashLooping
      expr: rate(kube_pod_container_status_restarts_total[5m]) > 0.1
      for: 5m
      labels:
        severity: critical
      
    - alert: PipelineFailing
      expr: rate(pipeline_failures_total[5m]) > 0.05
      for: 2m
      labels:
        severity: critical
      
    - alert: DiskAlmostFull
      expr: kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes > 0.85
      for: 5m
      labels:
        severity: critical
      
    - alert: PostgreSQLDown
      expr: pg_up == 0
      for: 1m
      labels:
        severity: critical
```

### Warning
```yaml
  - name: meeting-automation-warning
    rules:
    - alert: HighMemoryUsage
      expr: container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85
      for: 10m
      labels:
        severity: warning
      
    - alert: HighAPILatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
      for: 5m
      labels:
        severity: warning
      
    - alert: CeleryQueueBacklog
      expr: rabbitmq_queue_messages_ready > 50
      for: 10m
      labels:
        severity: warning
```

## 5. Grafana Dashboards

### Dashboard 1: Pipeline Overview
- **Panels**: Recording Uploads/h, Transcription Latency (p50/p95/p99), Pipeline Duration, Success Rate
- **Refresh**: 30s
- **Time Range**: 6h

### Dashboard 2: Infrastructure
- **Panels**: Node CPU/Memory/Disk, Pod Status, PVC Usage, Network I/O
- **Refresh**: 15s
- **Time Range**: 24h

### Dashboard 3: PostgreSQL
- **Panels**: Connections, Query Duration, Replication Lag, Database Size, Cache Hit Ratio
- **Refresh**: 30s
- **Time Range**: 6h

### Dashboard 4: Celery Workers
- **Panels**: Queue Length, Task Duration, Worker Memory, Failed Tasks, Worker Restarts
- **Refresh**: 15s
- **Time Range**: 6h

### Dashboard 5: MinIO/S3
- **Panels**: Storage Used, Upload/Download Rate, Error Rate, Bucket Size
- **Refresh**: 60s
- **Time Range**: 24h

## 6. Implementation-Status

| Komponente | Status | Nächstes |
|------------|--------|----------|
| Prometheus | ✅ Installiert | Custom Metrics implementieren |
| Grafana | ✅ Installiert (Port 31000) | Dashboards importieren |
| Node-Exporter | ✅ Auf beiden Nodes | — |
| Backend /metrics Endpoint | ⏳ Fehlt | Implementieren |
| Celery Custom Metrics | ⏳ Fehlt | Implementieren |
| Prometheus Rules (Alerts) | ⏳ Fehlt | YAML definieren |
| Loki/Promtail | ⏳ Fehlt | Braucht S3-Backend |
| Dashboards | ⏳ Fehlt | JSON importieren |

## 7. Nächste Schritte

1. **Backend `/metrics` Endpoint** — FastAPI mit `prometheus_client` Library
2. **Celery Custom Metrics** — Task-Duration, Queue-Length via Redis
3. **Prometheus AlertRules** — YAML mit Critical/Warning Alerts
4. **Grafana Dashboards** — JSON-Imports für 5 Dashboards
5. **Loki/Promtail** — Log-Aggregation (optional, braucht S3)
