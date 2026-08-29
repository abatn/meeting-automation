# Monitoring Guide — Meeting Automation

> Stand: 2026-07-03 | k3s Staging 2-Node Cluster

## Zugriff

| Service | URL | Login |
|---------|-----|-------|
| **Prometheus** | https://monitoring.meeting-automation.com | Kein Auth |
| **Grafana** | `kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring` | admin / prom-operator |
| **AlertManager** | `kubectl port-forward svc/kube-prometheus-stack-alertmanager 9093:9093 -n monitoring` | Kein Auth |

## Was läuft

| Komponente | Status | Targets |
|-----------|--------|---------|
| Prometheus | ✅ 17/19 UP | apiserver, coredns, kubelet (×6), node-exporter (×2), kube-state-metrics, alertmanager, grafana, operator |
| Grafana | ✅ Running | 3 Custom Dashboards (Phase 117) |
| AlertManager | ✅ Running | 286 Rules, 13 Firing |
| Backend /metrics | ❌ DOWN | Auth-Dependency blockiert Prometheus |

## PromQL Quick Reference

### Infrastruktur
```promql
# Node CPU Auslastung (%)
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Node Memory Auslastung (%)
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk Auslastung (%)
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100

# Pod Anzahl
count(kube_pod_info)

# Alle Targets UP/DOWN
up
```

### Application
```promql
# HTTP Requests pro Route
http_requests_total

# HTTP Fehler (5xx)
http_requests_total{code=~"5.."}

# HTTP Requests pro Sekunde
rate(http_requests_total[5m])

# Recording-Status
http_requests_total{route=~".*recording.*"}
```

### Alerts
```promql
# Aktive Firing Alerts
ALERTS{alertstate="firing"}

# Kritische Alerts
ALERTS{alertstate="firing", severity="critical"}

# Warning Alerts
ALERTS{alertstate="firing", severity="warning"}
```

## Custom Dashboards (Phase 117 — in Grafana)

| Dashboard | Inhalt |
|-----------|--------|
| **Pipeline Overview** | CPU, Memory, Disk (cadvisor-basiert) |
| **Intelligence** | API Requests, Pipeline-Metriken, Response Times |
| **Tenant Analytics** | Multi-Tenant client_id Metriken |

**Zugriff:** Grafana über NodePort 31000 oder `kubectl port-forward`

## Backend API (Phase 98 — im Frontend unter /admin/technik)

| Endpoint | Beschreibung |
|----------|-------------|
| `GET /admin/monitoring/cluster-overview` | Nodes, Pods, CPU%, Memory%, Disk% |
| `GET /admin/monitoring/alerts-summary` | total, critical, warning, alerts[] |
| `GET /admin/monitoring/recent-logs` | Loki-Logs |

## Firing Alerts (aktuell)

13 Alerts sind aktiv. Die wichtigsten:
- `BackendServiceDown` — False Positive (Backend läuft, kein /metrics Endpoint)
- `KubeControllerManagerDown` — k3s embedded Mode (False Positive)
- `KubeSchedulerDown` — k3s embedded Mode (False Positive)
- `Watchdog` — Heartbeat (gewollt)

## Troubleshooting

### Backend /metrics DOWN
Prometheus kann `/metrics` nicht erreichen weil der Endpoint `get_current_user` Dependency hat.
**Fix:** `/metrics` von Auth befreien oder Prometheus ServiceAccount in whiteliste aufnehmen.

### Grafana nicht erreichbar
`kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring`
Dann: `http://localhost:3000` → Login admin/prom-operator

### Alerts nicht sichtbar
Prometheus → Status → Rules prüfen ob Rules geladen sind.
Oder: `curl -sk https://monitoring.meeting-automation.com/api/v1/rules | jq '.data.groups | length'`
