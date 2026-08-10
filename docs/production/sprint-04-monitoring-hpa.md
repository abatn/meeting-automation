# Sprint 4: Monitoring + Auto-Scaling

> **Dauer:** ~3 Wochen | **Status:** ⬜ Offen
> **Komponenten:** Prometheus + Grafana + Loki (alle CNCF), HPA, PDB, PodAntiAffinity

## Monitoring: kube-prometheus-stack

### Installation

```bash
# Helm-Repo hinzufügen
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Installieren
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin123

# Prüfen
kubectl get pods -n monitoring
```

### Grafana zugänglich machen

```bash
# Als NodePort
kubectl patch svc kube-prometheus-stack-grafana -n monitoring \
  -p '{"spec":{"type":"NodePort"}}'

# Oder port-forward
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# URL: http://localhost:3001
# User: admin
# Pass: kubectl get secret -n monitoring kube-prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d
```

### Prometheus-Regel für Meeting-Automation

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: meeting-automation-backend
  namespace: meeting-automation
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
```

### Wichtige Dashboards

- **Kubernetes Cluster** — Node-Status, Pod-Health, Resource-Nutzung
- **Meeting Automation App** — Request-Rate, Latenz, Fehlerraten (via backend /metrics)
- **PostgreSQL** — Connections, Queries, Replication-Lag (via postgres-exporter)
- **Celery** — Queue-Length, Task-Duration, Failed Tasks

## Log-Aggregation: Loki

```bash
# Loki installieren (Teil von Grafana Stack)
helm upgrade --install loki grafana/loki \
  --namespace monitoring --create-namespace \
  --set loki.commonConfig.replication_factor=1 \
  --set singleBinary.replicas=1

# Promtail (Log-Collector) für alle Nodes
helm upgrade --install promtail grafana/promtail \
  --namespace monitoring \
  --set config.clients[0].url=http://loki:3100/loki/api/v1/push
```

## HorizontalPodAutoscaler (HPA)

### Backend

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: meeting-automation
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Frontend

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
  namespace: meeting-automation
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 2
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

## PodDisruptionBudget (PDB)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
  namespace: meeting-automation
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: backend
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: frontend-pdb
  namespace: meeting-automation
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: frontend
```

## PodAntiAffinity

```yaml
# Für alle Deployment/StatefulSet hinzufügen
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - backend   # jeweils eigene App
        topologyKey: kubernetes.io/hostname
```

## Validation

```bash
# HPA testen (Last simulieren)
kubectl run -it load-test --image=busybox -- /bin/sh -c "while true; do wget -q -O- http://backend:8000/api/health; done"

# HPA-Status beobachten
kubectl get hpa -n meeting-automation -w

# PDB testen (Node drain simulieren)
kubectl drain <node-name> --ignore-daemonsets

# Grafana-Dashboards
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80

# Logs via Loki (in Grafana Explore)
# Query: {app="backend"} |= "error"
```
