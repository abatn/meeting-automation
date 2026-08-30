# Port-7000-Konflikt Fix — 2026-08-29

## Zusammenfassung

Beim Revert auf Commit `8f2116ee` wurden fälschlicherweise **alle** YAML-Dateien aus `infrastructure/kubernetes/production/` auf den **Staging-Cluster** (OCI 158.180.18.110) angewendet. Dadurch entstand ein Namespace `meeting-automation` auf dem Staging-Cluster, der Port 7000 (hostPort) belegte und den Start von `livekit-egress-staging` verhinderte.

## Ursache

```
Revert-Befehl (2026-08-29):
  kubectl apply -f infrastructure/kubernetes/production/*.yaml  ← ALLES angewendet
  kubectl apply -f infrastructure/kubernetes/staging/*.yaml

Fehler:
  infrastructure/kubernetes/production/livekit-egress-deployment.yaml
  → Namespace: meeting-automation (Production!)
  → hostPort: 7000
  → Konflikt mit: meeting-automation-staging/livekit-egress-staging (hostPort 7000)
```

### Timeline

| Datum | Ereignis |
|-------|----------|
| 05.08 | Commit `8f2116ee`: Production-YAMLs im Repo, aber Skip-Regel verhindert Apply |
| 19.08 | Helm `livekit-egress` in Staging installiert |
| 20.08 | Production-YAMLs als "tot" gelöscht (Commit `102d5910`) |
| 29.08 | Revert auf `8f2116ee`: Production-YAMLs wiederhergestellt + **fälschlicherweise auf Staging angewendet** |
| 29.08 | `livekit-egress` (Production) blockiert Port 7000 → `livekit-egress-staging` Pending |

## Betroffene Ressourcen

### Namespace `meeting-automation` auf Staging-Cluster (gehört NICHT hierher)

| Ressource | Status | Problem |
|-----------|--------|---------|
| `livekit-egress` | CrashLoopBackOff | hostPort 7000 blockiert |
| `backend` (2 Pods) | CreateContainerConfigError | Production-Secrets fehlen |
| `celery-beat` | CreateContainerConfigError | Production-Secrets fehlen |
| `celery-worker` (2 Pods) | CreateContainerConfigError | Production-Secrets fehlen |
| `celery-worker-pro` (2 Pods) | Pending | Kein Speicher |
| `frontend` | ImagePullBackOff | Image existiert nicht |
| `livekit-server` | Pending | Kein Speicher |
| `meeting-db-1` | Pending | Kein Speicher |
| `minio-0` | Pending | Kein Speicher |
| `n8n` | Pending | Kein Speicher |
| `onlyoffice` | Running | Produktions-Config |
| `rabbitmq-0` | Pending | Kein Speicher |
| `redis` | CreateContainerConfigError | Production-Secrets fehlen |
| `n8n-nodeport` (31678) | aktiv | Blockiert Staging-Port |
| Ingress `meeting-automation.com` | aktiv | Produktions-Domain |
| CronJob `postgres-backup` | aktiv | Production-Backup |

### Namespace `meeting-automation-staging` (korrekt)

| Ressource | Status |
|-----------|--------|
| `livekit-egress-staging` | **Pending** (durch Port-Konflikt) |
| Alle anderen Pods | Running |

## Lösung

### Schritt 1: Namespace löschen

```bash
kubectl delete namespace meeting-automation
```

### Schritt 2: Verifikation

```bash
# Port 7000 frei?
kubectl get pods -A -o json | python3 -c "
import json,sys
for pod in json.load(sys.stdin)['items']:
    hn = pod['spec'].get('hostNetwork', False)
    for c in pod['spec'].get('containers', []):
        for p in c.get('ports', []):
            if p.get('hostPort') == 7000 and hn:
                print(f'{pod[\"metadata\"][\"namespace\"]}/{pod[\"metadata\"][\"name\"]}')
"

# livekit-egress-staging läuft?
kubectl get pods -n meeting-automation-staging -l app=livekit-egress-staging

# Staging unversehrt?
kubectl get pods -n meeting-automation-staging
```

### Schritt 3: Git-Bereinigung

Production-YAMLs aus dem Repo entfernen oder markieren:
- `infrastructure/kubernetes/production/livekit-egress-deployment.yaml`
- `infrastructure/kubernetes/production/livekit-egress-configmap.yaml`

## Verhinderung

Für zukünftige Reverts:
1. **Nur Staging-YAMLs** auf den Staging-Cluster anwenden
2. **Nur Production-YAMLs** auf den Production-Cluster anwenden
3. Deploy-Script muss production/staging klar trennen

## CI-Workflows: Longhorn-Bereinigung

Entfernt aus `e2e-tests.yml` und `deploy-production.yml`:
- Longhorn-Installation (`helm install longhorn`)
- `longhorn-cleanup` CronJob

Beibehalten:
- `ephemeral-storage-cleanup` CronJob (kube-system)
- `pod-garbage-collector` CronJob (kube-system)
- `metrics-server-patch` (kube-system)

## CI-Workflows: Longhorn/Velero Namespace-Konflikte

### Ursache

Zwei Dateien im staging/ Verzeichnis haben hardcoded Namespaces die nicht zu `-n meeting-automation-staging` passen:

| Datei | Hardcoded Namespace | Problem |
|-------|---------------------|---------|
| `longhorn-csi-autoscaler.yaml` | `longhorn-system` | Longhorn ist auf 0 skaliert → CronJob sinnlos |
| `velero-backup-repository.yaml` | `velero` | Velero braucht das Repository für Kopia-Backups |

### Fix

```yaml
# Vorher (falsch):
kubectl apply -f infrastructure/kubernetes/staging/longhorn-csi-autoscaler.yaml \
  -f infrastructure/kubernetes/staging/velero-backup-repository.yaml \
  -n meeting-automation-staging

# Nachher (korrekt):
# longhorn-csi-autoscaler.yaml → ENTFERNT (Longhorn auf 0 skaliert)
kubectl apply -f infrastructure/kubernetes/staging/velero-backup-repository.yaml -n velero
```

### Betroffene Ressourcen

| Ressource | Vorher | Nachher |
|-----------|--------|---------|
| `longhorn-csi-autoscaler` | Im Apply (falscher Namespace) | Entfernt |
| `velero-backup-repository` | Im Apply (falscher Namespace) | Separater Apply mit `-n velero` |

## CI-Workflows: Defekter Trigger

### Ursache

`deploy-production.yml` referenziert einen Workflow `Docker Build & Push`, der am 20.08 gelöscht wurde (Commit `102d5910`). Dieser Workflow war zuständig für:
- Docker-Image-Build (backend + frontend)
- Push nach Docker Hub

Nach der Löschung übernahm `e2e-tests.yml` (`E2E Tests & Deployment Pipeline`) diese Aufgabe. Der Trigger in `deploy-production.yml` wurde jedoch nicht aktualisiert.

### Fix

```yaml
# Vorher (kaputt):
on:
  workflow_run:
    workflows: ["Docker Build & Push"]

# Nachher (korrekt):
on:
  workflow_run:
    workflows: ["E2E Tests & Deployment Pipeline"]
```

### Betroffene Workflows

| Workflow | `name:` | Status |
|----------|---------|--------|
| `backend-ci.yml` | `Backend CI` | Tests only, kein Docker Push |
| `e2e-tests.yml` | `E2E Tests & Deployment Pipeline` | Baut + pushed Docker Images |
| `deploy-production.yml` | `Deploy Production` | Trigger korrigiert |
| `frontend-ci.yml` | `Frontend CI` | Lint + Build only |

## Reversibilität

- Namespace `meeting-automation` kann jederzeit neu erstellt werden
- Alle YAML-Dateien sind im Git unter `infrastructure/kubernetes/production/`
- Helm-Releases bleiben unberührt

## CI-Workflows: Fehlende Production-Resources

### Ursache

`deploy-production.yml` wendete seit Jul 28 (Commit `b3dfad55`) nur einen Teil der Production-Resources an. Drei Dateien fehlten in den `kubectl apply`-Befehlen:

| Datei | Typ | Funktion |
|-------|-----|----------|
| `onlyoffice-secrets.yaml` | Secret | OnlyOffice JWT + API-Key |
| `onlyoffice-custom-config.yaml` | ConfigMap | OnlyOffice Nginx-Konfiguration |
| `postgres-backup-cronjob.yaml` | CronJob | PostgreSQL Backup (täglich 02:00) |

### Fix

```yaml
# Vorher (lückenhaft):
for secret in backend-secrets postgres-secrets redis-secrets minio-secrets rabbitmq-secrets livekit-secrets n8n-secrets; do
kubectl apply -f backend-config.yaml -f livekit-configmap.yaml -f livekit-egress-configmap.yaml -f frontend-nginx-config.yaml
kubectl apply -f cnpg-cluster.yaml

# Nachher (vollständig):
for secret in backend-secrets postgres-secrets redis-secrets minio-secrets rabbitmq-secrets livekit-secrets n8n-secrets onlyoffice-secrets; do
kubectl apply -f backend-config.yaml -f livekit-configmap.yaml -f livekit-egress-configmap.yaml -f frontend-nginx-config.yaml -f onlyoffice-custom-config.yaml
kubectl apply -f cnpg-cluster.yaml
kubectl apply -f postgres-backup-cronjob.yaml
```

### Betroffene Ressourcen

| Ressource | Vorher | Nachher |
|-----------|--------|---------|
| `onlyoffice-secrets` | Nur manuell | Im Secrets-Loop |
| `onlyoffice-custom-config` | Fehlte | Nach ConfigMaps |
| `postgres-backup-cronjob` | Fehlte | Nach CNPG-Cluster |

## CI-Workflows: Explizite Dateiliste (e2e-tests.yml)

### Ursache

`kubectl apply -f infrastructure/kubernetes/staging/` traversiert rekursiv und trifft 5 Helm-Values-Dateien ohne `apiVersion`/`kind`:

```
error validating data: [apiVersion not set, kind not set]
```

Betroffene Dateien:
- `egress-values.yaml` (LiveKit Egress Helm Values)
- `livekit-server-values.yaml` (LiveKit Server Helm Values)
- `longhorn-values.yaml` (Longhorn Helm Values)
- `velero-values.yaml` (Velero Helm Values)
- `k3s-config.yaml` (k3s Cluster Config)

### Fix

Rekursives `kubectl apply -f staging/` → explizite Dateiliste mit 53 valid K8s-Resources (40 App + 13 Monitoring).

## CI-Workflows: Fehlende Monitoring-CRDs

### Ursache

Die kube-prometheus-stack CRDs (PrometheusRule, ServiceMonitor) wurden gelöscht als der Monitoring-Stack auf 0 skaliert wurde. Die CI-Dateiliste in e2e-tests.yml applyt diese Dateien trotzdem:

```
error: the server doesn't have a resource type "PrometheusRule"
error: the server doesn't have a resource type "ServiceMonitor"
```

Betroffene Dateien (13 Stück):
- `grafana-dashboard-intelligence.yaml` → ConfigMap
- `grafana-dashboard-pipeline.yaml` → ConfigMap
- `grafana-dashboard-tenants.yaml` → ConfigMap
- `grafana-datasource-loki.yaml` → ConfigMap
- `grafana-external-service.yaml` → Service
- `monitoring-ingress.yaml` → Ingress
- `prometheus-adapter-config.yaml` → ConfigMap
- `prometheus-recording-rules.yaml` → PrometheusRule
- `prometheus-rules.yaml` → PrometheusRule
- `prometheus-slo-rules.yaml` → PrometheusRule
- `service-monitor.yaml` → ServiceMonitor
- `velero-prometheusrule.yaml` → PrometheusRule
- `velero-servicemonitor.yaml` → ServiceMonitor

### Fix

Entferne den gesamten monitoring/ Block aus der expliziten Dateiliste in e2e-tests.yml. Der Monitoring-Stack ist auf 0 skaliert — weder CRDs noch ConfigMaps/Service/Ingress werden gebraucht.
