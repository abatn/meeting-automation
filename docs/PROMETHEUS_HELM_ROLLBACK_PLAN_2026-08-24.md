# Prometheus Helm-Upgrade Rollback-Plan

**Datum:** 2026-08-24
**Betrifft:** kube-prometheus-stack Helm-Upgrade (scrape intervals)
**Server:** Production (169.58.83.32) + Staging (158.180.18.110)

---

## VOR DEM UPGRADE

### Backup (BEFORE任何 Änderung)

```bash
# Production
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  # 1. Prometheus CRD sichern
  kubectl get prometheus -n monitoring -o yaml > /tmp/prometheus-crd-backup.yaml
  
  # 2. Alle ServiceMonitors sichern
  kubectl get servicemonitor -A -o yaml > /tmp/servicemonitors-backup.yaml
  
  # 3. Helm Values sichern (falls verfügbar)
  helm get values kube-prometheus-stack -n monitoring > /tmp/helm-values-backup.yaml 2>/dev/null || echo 'Helm Values nicht verfügbar'
  
  # 4. Aktuelle Targets sichern
  curl -sk https://localhost:6443/metrics | grep '^up{' > /tmp/prometheus-targets-backup.txt
  
  # 5. Prometheus StatefulSet sichern
  kubectl get statefulset prometheus-kube-prometheus-stack-prometheus -n monitoring -o yaml > /tmp/prometheus-sts-backup.yaml
  
  echo 'Backup abgeschlossen: /tmp/prometheus-*'
"
```

### Ist-Zustand dokumentieren

```bash
# Production — Ist-Zustand
ssh root@169.58.83.32 "
  echo '=== SCRAPE INTERVALS ==='
  kubectl get servicemonitor -A -o json | python3 -c \"
import sys, json
data = json.load(sys.stdin)
for item in data['items']:
    name = item['metadata']['name']
    ns = item['metadata']['namespace']
    for ep in item['spec'].get('endpoints', []):
        interval = ep.get('interval', 'GLOBAL DEFAULT')
        port = ep.get('port', 'N/A')
        print(f'{ns}/{name}: port={port} interval={interval}')
\"
  
  echo '=== PROMETHEUS CRD ==='
  kubectl get prometheus -n monitoring -o yaml | grep -E 'scrapeInterval|evaluationInterval'
  
  echo '=== TARGETS UP ==='
  kubectl exec -n monitoring prometheus-kube-prometheus-stack-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/targets' 2>/dev/null | python3 -c \"
import sys, json
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(f\\\"{t['labels'].get('job','?')}: {t['health']}\\\")
\" || echo 'Targets nicht abrufbar'
"
```

---

## UPGRADE-DURCHFÜHRUNG

### Schritt 1: Helm Values-Datei anwenden

```bash
# Production
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  # Helm Repo updaten
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
  helm repo update
  
  # Upgrade mit neuen Values
  helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
    -n monitoring \
    --reuse-values \
    --values /tmp/prometheus-values.yaml \
    --timeout 5m \
    --wait
  
  echo 'Helm Upgrade abgeschlossen'
"
```

### Schritt 2: Monitoring-Configs neu anwenden

```bash
# Production
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  # ServiceMonitors aktualisieren
  kubectl apply -f infrastructure/kubernetes/production/monitoring/service-monitor.yaml -n monitoring
  kubectl apply -f infrastructure/kubernetes/production/monitoring/velero-servicemonitor.yaml -n monitoring
  
  # Prometheus CRD patchen (Global Default)
  kubectl patch prometheus kube-prometheus-stack-prometheus -n monitoring \
    --type merge \
    -p '{\"spec\":{\"scrapeInterval\":\"90s\",\"evaluationInterval\":\"30s\"}}'
  
  echo 'Monitoring-Configs aktualisiert'
"
```

### Schritt 3: Rollout abwarten

```bash
# Production
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  # StatefulSet Rollout abwarten
  kubectl rollout status statefulset/prometheus-kube-prometheus-stack-prometheus \
    -n monitoring --timeout=300s
  
  echo 'Prometheus Rollout abgeschlossen'
"
```

### Schritt 4: Verifikation

```bash
# Production — Post-Upgrade Check
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  echo '=== NEUE SCRAPE INTERVALS ==='
  kubectl get servicemonitor -A -o json | python3 -c \"
import sys, json
data = json.load(sys.stdin)
for item in data['items']:
    name = item['metadata']['name']
    ns = item['metadata']['namespace']
    for ep in item['spec'].get('endpoints', []):
        interval = ep.get('interval', 'GLOBAL DEFAULT')
        port = ep.get('port', 'N/A')
        print(f'{ns}/{name}: port={port} interval={interval}')
\"
  
  echo '=== PROMETHEUS CRD ==='
  kubectl get prometheus -n monitoring -o yaml | grep -E 'scrapeInterval|evaluationInterval'
  
  echo '=== PROMETHEUS POD STATUS ==='
  kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus
  
  echo '=== TARGETS ==='
  curl -s http://localhost:9090/api/v1/targets 2>/dev/null | python3 -c \"
import sys, json
data = json.load(sys.stdin)
up = sum(1 for t in data['data']['activeTargets'] if t['health'] == 'up')
down = sum(1 for t in data['data']['activeTargets'] if t['health'] == 'down')
print(f'Targets: {up} UP, {down} DOWN')
for t in data['data']['activeTargets']:
    if t['health'] == 'down':
        print(f'  DOWN: {t[\"labels\"].get(\"job\",\"?\")} — {t[\"lastError\"][:80]}')
\" || echo 'Targets nicht abrufbar'
  
  echo '=== k3s CPU ==='
  ps -p \$(pgrep k3s | head -1) -o pid,pcpu --no-headers
"
```

---

## ROLLBACK (wenn Upgrade fehlschlägt)

### Sofortiger Rollback (innerhalb 5 Minuten)

```bash
# Production — SOFORTIGER ROLLBACK
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  echo '=== ROLLBACK: Helm ==='
  helm rollback kube-prometheus-stack 0 -n monitoring --wait --timeout 3m
  
  echo '=== ROLLBACK: Prometheus CRD ==='
  kubectl apply -f /tmp/prometheus-crd-backup.yaml
  
  echo '=== ROLLBACK: ServiceMonitors ==='
  kubectl apply -f /tmp/servicemonitors-backup.yaml
  
  echo '=== ROLLBACK: StatefulSet ==='
  kubectl apply -f /tmp/prometheus-sts-backup.yaml
  
  echo '=== VERIFIKATION ==='
  kubectl get pods -n monitoring
  kubectl get servicemonitor -A
  kubectl get prometheus -n monitoring -o yaml | grep scrapeInterval
  
  echo 'Rollback abgeschlossen'
"
```

### Helm Rollback (Release-History)

```bash
# Prüfe verfügbare Revisions
helm history kube-prometheus-stack -n monitoring

# Rollback zu letzter funktionierender Revision
helm rollback kube-prometheus-stack <REVISION> -n monitoring --wait

# Oder: Rollback zu Revision 1 (erste Installation)
helm rollback kube-prometheus-stack 1 -n monitoring --wait
```

### Vollständiger Neustart (letzter Ausweg)

```bash
# Production — PROMETHEUS KOMPLETT NEU STARTEN
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  echo '=== PROMETHEUS STATEFULSET NEU STARTEN ==='
  kubectl delete statefulset prometheus-kube-prometheus-stack-prometheus -n monitoring
  
  # Warte auf automatische Neuerstellung
  kubectl rollout status statefulset/prometheus-kube-prometheus-stack-prometheus \
    -n monitoring --timeout=300s
  
  echo '=== PROMETHEUS CRD RESTAURIEREN ==='
  kubectl apply -f /tmp/prometheus-crd-backup.yaml
  
  echo '=== SERVICE MONITORS RESTAURIEREN ==='
  kubectl apply -f /tmp/servicemonitors-backup.yaml
  
  echo '=== VERIFIKATION ==='
  kubectl get pods -n monitoring
  kubectl get targets 2>/dev/null || curl -s http://localhost:9090/api/v1/targets | python3 -c \"
import sys, json
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(f\\\"{t['labels'].get('job','?')}: {t['health']}\\\")
\"
  
  echo 'Neustart abgeschlossen'
"
```

---

## ROLLBACK-ENTSCHEIDUNG

| Symptom | Aktion | Priorität |
|---------|--------|-----------|
| Prometheus Pod crasht | Helm rollback + CRD restore | 🔴 SOFORT |
| Targets DOWN | ServiceMonitor restore | 🟡 5 Min |
| Grafana nicht erreichbar | Prometheus Pod neustarten | 🟡 5 Min |
| Alertmanager nicht erreichbar | StatefulSet neustarten | 🟡 10 Min |
| k3s CPU steigt >10% | Prometheus CRD restore (scrapeInterval zurücksetzen) | 🟡 5 Min |
| Monitoring-Lücke >5 Min | Helm rollback | 🔴 SOFORT |

---

## POST-ROLLBACK VERIFIKATION

```bash
# Nach jedem Rollback ausführen
ssh root@169.58.83.32 "
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  
  echo '=== POD STATUS ==='
  kubectl get pods -n monitoring
  
  echo '=== TARGETS ==='
  curl -s http://localhost:9090/api/v1/targets | python3 -c \"
import sys, json
data = json.load(sys.stdin)
up = sum(1 for t in data['data']['activeTargets'] if t['health'] == 'up')
down = sum(1 for t in data['data']['activeTargets'] if t['health'] == 'down')
print(f'Targets: {up} UP, {down} DOWN')
\"
  
  echo '=== SCRAPE INTERVALS ==='
  kubectl get prometheus -n monitoring -o yaml | grep scrapeInterval
  
  echo '=== k3s CPU ==='
  ps -p \$(pgrep k3s | head -1) -o pid,pcpu --no-headers
  
  echo '=== GRAFANA ==='
  kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana
  
  echo '=== ALERTMANAGER ==='
  kubectl get pods -n monitoring -l app.kubernetes.io/name=alertmanager
"
```

---

## BEKANNTE PROBLEME

### 1. Helm Release-Metadaten verloren

**Problem:** `helm list -n monitoring` → leer. `helm get values` → leer.

**Ursache:** Release-Metadaten wurden beim k3s-Neustart oder Namespace-Cleanup gelöscht.

**Lösung:**
```bash
# Helm Release manuell wiederherstellen
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set prometheus.prometheusSpec.hostNetwork=true \
  --set prometheus.prometheusSpec.dnsPolicy=ClusterFirstWithHostNet \
  --set prometheus.service.port=9090 \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=local-path \
  --dry-run --debug  # Nur prüfen, nicht ausführen
```

### 2. scrapeInterval in Helm Values vs. Prometheus CRD

**Problem:** Helm Values setzen `scrapeInterval`, aber Prometheus CRD überschreibt es.

**Lösung:** Prometheus CRD NICHT manuell patchen nach Helm-Upgrade. Helm steuert die CRD.

### 3. kubelet 10s Interval (Cadvisor)

**Problem:** Ein kubelet-Endpoint hat `interval: 10s` (explizit in Helm-Values).

**Lösung:** In `prometheus-values.yaml` überschreiben:
```yaml
kubelet:
  serviceMonitor:
    interval: 120s  # Überschreibt 10s
```

---

## ZUSAMMENFASSUNG

| Phase | Aktion | Dauer |
|-------|--------|-------|
| **Vorher** | Backup + Ist-Zustand | 5 Min |
| **Upgrade** | Helm Values anwenden | 2 Min |
| **Upgrade** | Monitoring-Configs patchen | 1 Min |
| **Upgrade** | Rollout abwarten | 5 Min |
| **Verifikation** | Targets prüfen | 2 Min |
| **Gesamt** | | **15 Min** |

| Phase | Aktion | Dauer |
|-------|--------|-------|
| **Rollback** | Helm rollback + CRD restore | 5 Min |
| **Rollback** | Verifikation | 2 Min |
| **Gesamt** | | **7 Min** |
