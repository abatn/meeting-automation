# Prometheus Scrape-Interval Upgrade — Ergebnisse

**Datum:** 2026-08-25
**Server:** Production (169.58.83.32)
**Helm Chart:** kube-prometheus-stack v88.1.5 (app v0.93.0)

---

## Zusammenfassung

Per-target Scrape-Intervalle via Helm-Values implementiert. **k3s CPU von 86.7% auf 81.0% gesenkt (−5.7%). Load Average von 5.83 auf 3.16 (−46%).**

---

## Vorher / Nachher

| Metrik | Vorher (30s global) | Nachher (per-target) | Differenz |
|--------|--------------------|--------------------|-----------|
| **Prometheus CPU** | 25.9% | 26.0% | ~gleich |
| **k3s CPU** | 86.7% | 81.0% | **−5.7%** ✅ |
| **Load Average** | 5.83 | 3.16 | **−46%** ✅ |
| **Prometheus RSS** | 1,038 MB | 1,006 MB | −3% |
| **Targets UP** | 15 | 15 | unverändert ✅ |
| **Targets DOWN** | 0 | 0 | unverändert ✅ |
| **scrapeInterval (Global)** | 30s | 90s | 3× seltener |
| **evaluationInterval** | 30s | 30s | unverändert |

---

## Per-Target Scrape-Intervalle

| Target | Vorher | Nachher | Speedup |
|--------|--------|---------|---------|
| k3s API-Server | 30s | **90s** | 3× |
| kubelet (Cadvisor) | **10s** 🔴 | **120s** | **12×** |
| kubelet (other) | 30s | **120s** | 4× |
| Node-Exporter | 30s | **120s** | 4× |
| CoreDNS | 30s | **60s** | 2× |
| kube-controller-manager | 30s | **60s** | 2× |
| kube-scheduler | 30s | **60s** | 2× |
| kube-proxy | 30s | **120s** | 4× |
| kube-state-metrics | 30s | **60s** | 2× |
| Alertmanager | 30s | **60s** | 2× |
| Prometheus Self | 30s | **60s** | 2× |
| Prometheus Operator | 30s | **60s** | 2× |
| Grafana | 30s | **120s** | 4× |
| Backend | 30s | 30s | unverändert |
| Velero | 60s | 60s | unverändert |

---

## Durchführung

### Schritt 1: Helm Values-Datei erstellt

**Datei:** `infrastructure/kubernetes/production/prometheus-values.yaml`

Enthält per-target Intervalle:
- `kubeApiServer.serviceMonitor.interval: 90s`
- `kubelet.serviceMonitor.interval: 120s`
- `nodeExporter.serviceMonitor.interval: 120s`
- `coreDns.serviceMonitor.interval: 60s`
- `kubeControllerManager.serviceMonitor.interval: 60s`
- `kubeScheduler.serviceMonitor.interval: 60s`
- `kubeProxy.serviceMonitor.interval: 120s`
- `kubeStateMetrics.serviceMonitor.interval: 60s`
- `alertmanager.serviceMonitor.interval: 60s`
- `prometheusOperator.serviceMonitor.interval: 60s`
- `grafana.serviceMonitor.interval: 120s`

### Schritt 2: Helm-Upgrade durchgeführt

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --reuse-values \
  --values /tmp/prometheus-values.yaml \
  --timeout 5m --wait
```

**Ergebnis:** ✅ Upgrade erfolgreich, 15/15 Targets UP

### Schritt 3: Global scrapeInterval gepatcht

```bash
kubectl patch prometheus kube-prometheus-stack-prometheus -n monitoring \
  --type merge \
  -p '{"spec":{"scrapeInterval":"90s"}}'
```

**Ergebnis:** ✅ Global Default von 30s auf 90s geändert

---

## Bekanntes Problem

### Global scrapeInterval nicht in Helm Values

Der `scrapeInterval: 90s` wurde per `kubectl patch` gesetzt, nicht über Helm. Bei nächstem `helm upgrade --reuse-values` wird er wieder auf 30s zurückgesetzt.

**Lösung:** In `prometheus-values.yaml` muss `prometheus.prometheusSpec.scrapeInterval: 90s` ergänzt werden.

---

## Was wurde geändert

| Datei | Änderung |
|-------|----------|
| `infrastructure/kubernetes/production/prometheus-values.yaml` | NEU — per-target scrape intervals |
| `docs/PROMETHEUS_HELM_ROLLBACK_PLAN_2026-08-24.md` | NEU — Rollback-Plan |
| `docs/PROMETHEUS_SCRAPE_INTERVAL_RESULTS_2026-08-25.md` | NEU — diese Datei |

---

## Commits

```
2ff8ce96 feat(prometheus): per-target scrape intervals für Production
32dacc25 docs(prometheus): Helm-Upgrade Rollback-Plan für scrape intervals
```

---

## Nächste Schritte

1. **Global scrapeInterval in Helm Values korrigieren** (nicht nur CRD patchen)
2. **Staging prüfen** — braucht es ein Upgrade?
3. **Monitoring-Lücke akzeptieren** — max 120s (kubelet/node-exporter) ist für Prod OK
4. **Prometheus CPU beobachten** — nach 24h nochmals messen

---

## Risiko-Bewertung

| Risiko | Bewertung | Grund |
|--------|-----------|-------|
| Monitoring-Lücke >120s | 🟡 Mittel | kubelet/node-exporter: 120s |
| k3s CPU steigt wieder | 🟢 Niedrig | Scrape-Intervalle sind stabil |
| Prometheus Data Verlust | 🟢 Kein | PVC bleibt erhalten |
| Rollback möglich | ✅ Ja | `helm rollback kube-prometheus-stack 0` |
