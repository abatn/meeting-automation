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
