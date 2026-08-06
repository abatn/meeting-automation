# Phase 190: Prometheus hostNetwork Fix — alle LESSONS aus .loop.md

**Date:** 2026-08-05
**Server:** OCI Staging (158.180.18.110 / 10.0.0.191) — ARM64, k3s v1.36.2+k3s1
**Referenz:** Phase 189 (metrics-server, exakt dasselbe Muster)

## Problem
Alle 12/15 Prometheus scrape targets DOWN. Root Cause: kube-router iptables chains defekt (iptables-nft / xtables Inkompatibilität auf Oracle UEK Kernel 6.12.0).

Pod-to-pod TCP via direkte IPs: "no route to host". Host-to-pod: funktioniert. Pod-to-Service (ClusterIP): funktioniert.

## Phase-189-Referenz — bewiesenes Muster

Metrics-Server hatte EXAKT dasselbe Problem (Phase 189, .loop.md Zeile 124-168):
- Pod (10.42.0.x) → kubelet (10.0.0.191:10250) → "no route to host"
- OCI VNIC blockiert Pod-CIDR→Node-IP Traffic
- Fix: `hostNetwork=true` + `secure-port=4443` + manuelle EndpointSlice

**Dasselbe Muster gilt für Prometheus.**

## Lessons aus .loop.md die EINGEBAUT werden müssen

| Lesson | Quelle | Auswirkung auf Prometheus |
|--------|--------|--------------------------|
| **MS1**: OCI VNIC blockiert Pod→Node Traffic | Phase 189 | hostNetwork umgeht Pod-Netzwerk |
| **MS2**: hostNetwork + Port-Konflikt | Phase 189 | Port 9090 muss frei sein (geprüft: ✅ frei) |
| **MS5**: Änderungen gehören ins Git | Phase 189 | Helm-Values + Recovery-Script in Git |
| **DNI1**: Hardcoded IPs verboten | Phase 189b | Keine hardcoded IPs im Plan |
| **DNI2**: HostNetwork-Pod-IP ≠ Cluster-Pod-IP | Phase 189b | Prometheus Pod-IP wird Node-IP → ServiceMonitor-Auswirkung |
| **DNS**: hostNetwork nutzt Host-DNS | Phase 40/135 | `dnsPolicy: ClusterFirstWithHostNet` für K8s Service-Namen |
| **NP-Bypass**: hostNetwork-Pods umgehen NP | Phase 95/122 | Prometheus scraped ungehindert (gewollt) |

## Auswirkungen von hostNetwork auf Prometheus

### Was sich ändert
| Komponente | Vorher | Nachher |
|------------|--------|---------|
| Prometheus Pod-IP | 10.42.0.61 (Pod-Netz) | 10.0.0.191 (Node-IP) |
| DNS-Auflösung | CoreDNS (K8s Services) | Host-DNS → braucht `dnsPolicy: ClusterFirstWithHostNet` |
| NetworkPolicy | Wird respektiert | Wird umgangen (gewollt für Monitoring) |
| Port 9090 | Nur im Pod-Netz | Auf dem Host gebunden |

### Was gleich bleibt
| Komponente | Status |
|------------|--------|
| Service `kube-prometheus-stack-prometheus` (ClusterIP 10.43.132.228) | Funktioniert weiterhin (routet zu Node-IP) |
| Headless Service `prometheus-operated` | Funktioniert weiterhin (1 Replica, kein Clustering) |
| Grafana Datasource `http://kube-prometheus-stack-prometheus.monitoring:9090` | Funktioniert weiterhin (via Service) |
| Alertmanager Verbindung | Funktioniert weiterhin (via Service) |
| Ingress `monitoring.meeting-automation.com` | Funktioniert weiterhin (nginx → Service → Pod) |
| PVC (local-path, 10Gi, 15d Retention) | Wird NICHT berührt |

### Risiko-Bewertung
| Risiko | Bewertung | Grund |
|--------|-----------|-------|
| Port 9090 Konflikt | ✅ Keiner | `ss -tlnp` zeigt nur localhost (kubectl port-forward) |
| Port 8080 Konflikt | ✅ Keiner | Nichts auf 8080 |
| Prometheus Data Verlust | ✅ Kein | PVC bleibt erhalten (local-path) |
| Grafana Ausfall | ✅ Kein | Zugriff via Service (unverändert) |
| Alertmanager Ausfall | ✅ Kein | Zugriff via Service (unverändert) |
| NetworkPolicy Enforcement | ⚠️ Bewusst | Prometheus umgeht NP (gewollt für Monitoring) |

## Pipeline-Status — NICHT in CI/CD

| Ressource | Deployed via | In Pipeline? |
|-----------|-------------|--------------|
| kube-prometheus-stack Helm Release | Manuell (`helm install`) | ❌ Nein |
| Prometheus CRD (hostNetwork) | Helm Values | ❌ `hostNetwork: false` |
| Prometheus Ingress | `kubectl apply -f .../staging/` | ✅ Ja |
| Grafana Dashboards | `kubectl apply -f .../staging/` | ✅ Ja |
| PrometheusRules | `kubectl apply -f .../staging/` | ✅ Ja |
| ServiceMonitor (backend) | `kubectl apply -f .../staging/` | ✅ Ja |

**Fazit:** kube-prometheus-stack ist NICHT Teil der CI/CD Pipeline. Er wurde manuell installiert. Der hostNetwork-Fix MUSS per `helm upgrade` ausgeführt werden — manueller Schritt.

## Durchführungsplan

### Schritt 1 — VOR-Check (READ-only)
```bash
# Port 9090 prüfen
sudo ss -tlnp | grep 9090

# Aktuelle Helm Values prüfen
sudo /usr/local/bin/helm get values kube-prometheus-stack -n monitoring --kubeconfig /etc/rancher/k3s/k3s.yaml

# Aktuelle Prometheus Pod-IP prüfen
sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/kubectl get pod prometheus-kube-prometheus-stack-prometheus-0 -n monitoring -o jsonpath='{.status.podIP}'
```

### Schritt 2 — Helm Values updaten
```bash
sudo /usr/local/bin/helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --kubeconfig /etc/rancher/k3s/k3s.yaml \
  --reuse-values \
  --set prometheus.prometheusSpec.hostNetwork=true
```
**Was passiert:** Prometheus CRD wird geändert → StatefulSet Pod wird neu gestartet mit `hostNetwork: true`.

### Schritt 3 — Pod-Neustart abwarten
```bash
sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/kubectl rollout status sts/prometheus-kube-prometheus-stack-prometheus -n monitoring --timeout=120s
```

### Schritt 4 — Verifikation
```bash
# hostNetwork prüfen
sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/kubectl get pod prometheus-kube-prometheus-stack-prometheus-0 -n monitoring -o jsonpath='{.spec.hostNetwork}'

# Pod-IP = Node-IP?
sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/kubectl get pod prometheus-kube-prometheus-stack-prometheus-0 -n monitoring -o jsonpath='{.status.podIP}'

# Prometheus Targets prüfen (sollten UP sein)
curl -s http://10.0.0.191:9090/api/v1/targets | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"{t['labels'].get('job','?')}: {t['health']}\") for t in d['data']['activeTargets']]"
```

### Schritt 5 — CI/CD Pipeline anpassen (MS5 Lessons)
Helm Upgrade in Pipeline aufnehmen für zukünftige Deployments:
```yaml
# In .github/workflows/e2e-tests.yml, nach Longhorn-Install:
- name: Ensure kube-prometheus-stack hostNetwork
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-staging
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update
    helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
      -n monitoring --kubeconfig $(pwd)/kubeconfig-staging \
      --reuse-values --set prometheus.prometheusSpec.hostNetwork=true \
      --install --timeout 5m || echo "Warning: Prometheus helm upgrade failed"
```

### Schritt 6 — Git-commit
Änderungen in Git dokumentieren:
- `docs/MONITORING_FIX_PROMETHEUS_HOSTNETWORK_2026-08-05.md` (diese Datei)
- `.github/workflows/e2e-tests.yml` (Pipeline-Integration)

## Rollback
```bash
sudo /usr/local/bin/helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --kubeconfig /etc/rancher/k3s/k3s.yaml \
  --reuse-values \
  --set prometheus.prometheusSpec.hostNetwork=false
```

## Option B — Root Cause Fix (später)
kube-router deaktivieren: `disable-network-policy: true` in `/etc/rancher/k3s/config.yaml` + `systemctl restart k3s`. Entfernt defekte iptables Chains komplett. NetworkPolicies in staging namespace不再 enforced.
