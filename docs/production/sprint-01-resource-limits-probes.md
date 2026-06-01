# Sprint 1: Resource Limits + Health Probes

> **Dauer:** Sofort | **Status:** ⬜ Offen
> **Betroffen:** 9/11 Workloads ohne Limits, 7/11 ohne Probes

## Resource Limits

Referenzwerte aus `docker-compose.yml`:

```yaml
resources:
  limits:
    memory: <value>
    cpu: <value>
  requests:
    memory: <value>
    cpu: <value>
```

### Limit-Tabelle

| Workload | Memory Limit | CPU Limit | Memory Request | CPU Request |
|---|---|---|---|---|
| postgres | 512Mi | 0.5 | 256Mi | 100m |
| redis | 512Mi | 0.5 | 128Mi | 50m |
| rabbitmq | 512Mi | 0.5 | 256Mi | 100m |
| minio | 512Mi | 0.5 | 256Mi | 100m |
| n8n | 1Gi | 0.5 | 512Mi | 200m |
| onlyoffice | 2Gi | 1.0 | 1Gi | 500m |
| celery-beat | 512Mi | 0.5 | 256Mi | 100m |
| celery-worker | 1Gi | 1.0 | 512Mi | 200m |
| frontend | 512Mi | 0.5 | 128Mi | 50m |
| traefik | 256Mi | 0.5 | 128Mi | 100m |
| backend | 1Gi | 0.5 | 256Mi | 100m |

### YAML-Beispiel (postgres-statefulset.yaml)

```yaml
resources:
  limits:
    memory: "512Mi"
    cpu: "0.5"
  requests:
    memory: "256Mi"
    cpu: "100m"
```

## Health Probes

| Workload | Probe Type | Command/Path | Delay | Period | Timeout |
|---|---|---|---|---|---|
| celery-beat | liveness | `celery -A app.tasks.celery_app inspect ping` | 30s | 30s | 5s |
| celery-worker | liveness | `celery -A app.tasks.celery_app inspect ping` | 30s | 30s | 5s |
| frontend | liveness | httpGet `/` port 80 | 15s | 15s | 5s |
| n8n | liveness | httpGet `/healthz` port 5678 | 30s | 30s | 5s |
| redis | liveness | `redis-cli ping` | 15s | 15s | 3s |
| traefik | liveness | httpGet `/ping` port 8080 | 10s | 10s | 3s |
| minio | liveness | httpGet `/minio/health/live` port 9000 | 15s | 15s | 5s |
| rabbitmq | liveness | `rabbitmq-diagnostics check_running` | 30s | 30s | 15s |

### YAML-Beispiel (Probe)

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 5678
  initialDelaySeconds: 30
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `infrastructure/kubernetes/redis-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/minio-statefulset.yaml` | resources + probes |
| `infrastructure/kubernetes/rabbitmq-statefulset.yaml` | resources + liveness probe |
| `infrastructure/kubernetes/n8n-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/onlyoffice-deployment.yaml` | resources |
| `infrastructure/kubernetes/celery-beat-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/celery-worker-deployment.yaml` | probes |
| `infrastructure/kubernetes/frontend-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/traefik-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/postgres-statefulset.yaml` | resources |

## Validation

```bash
# Limits prüfen
kubectl get pods -n meeting-automation -o json | jq '.items[].spec.containers[].resources'

# Probes prüfen
kubectl get pods -n meeting-automation -o json | jq '.items[].spec.containers[].livenessProbe'

# Simuliere Fail (Probe-Test)
kubectl exec -n meeting-automation deploy/backend -- kill 1
# Erwartet: Pod wird neu gestartet (RESTARTS +1)
```
