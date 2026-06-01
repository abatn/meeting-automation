# Sprint 5: GitOps + Environments + Secrets

> **Dauer:** ~4 Wochen | **Status:** ⬜ Offen
> **Komponenten:** ArgoCD (CNCF), SOPS (Mozilla), Sealed Secrets (Bitnami), Kustomize (CNCF)

## GitOps: ArgoCD

### Installation

```bash
# ArgoCD installieren
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# CLI installieren
curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x /usr/local/bin/argocd

# Initiales Passwort holen
kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d

# Zugriff
kubectl port-forward -n argocd svc/argocd-server 8080:443
# URL: https://localhost:8080
# User: admin
```

### Repository-Struktur

```
├── clusters/
│   ├── dev/                    # kind/Minikube
│   │   └── kustomization.yaml
│   └── prod/                   # On-Prem / Cloud
│       └── kustomization.yaml
├── applications/
│   └── meeting-automation/
│       ├── dev.yaml            # ArgoCD Application (dev)
│       └── prod.yaml           # ArgoCD Application (prod)
└── config/
    └── meeting-automation/
        ├── base/               # Gemeinsame Basis
        │   ├── kustomization.yaml
        │   ├── deployment.yaml
        │   ├── service.yaml
        │   ├── ingress.yaml
        │   └── configmap.yaml
        ├── overlays/
        │   ├── dev/            # Dev-spezifisch
        │   │   ├── kustomization.yaml
        │   │   └── replica-count.yaml
        │   └── prod/           # Prod-spezifisch
        │       ├── kustomization.yaml
        │       ├── replica-count.yaml
        │       └── resources.yaml
        └── secrets/
            ├── .sops.yaml      # SOPS-Konfiguration
            ├── secrets.dev.enc.yaml
            └── secrets.prod.enc.yaml
```

### ArgoCD Application (dev)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: meeting-automation-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourorg/meeting-automation.git
    targetBranch: develop
    path: config/meeting-automation/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: meeting-automation-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### ArgoCD Application (prod)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: meeting-automation-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourorg/meeting-automation.git
    targetBranch: main
    path: config/meeting-automation/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: meeting-automation-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### Kustomize-Basis (base/kustomization.yaml)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
commonLabels:
  app: meeting-automation
resources:
- deployment.yaml
- service.yaml
- ingress.yaml
- configmap.yaml
```

### Kustomize-Overlay (overlays/prod/kustomization.yaml)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- ../../base
patches:
- path: replica-count.yaml
- path: resources.yaml
namespace: meeting-automation-prod
```

## Secret Management

### Option 1: SOPS (Mozilla) — bereits im Einsatz

```bash
# .sops.yaml Konfiguration
creation_rules:
  - path_regex: secrets/prod/.*\.yaml
    age: age1...
  - path_regex: secrets/dev/.*\.yaml
    age: age2...

# Secret verschlüsseln
sops --encrypt secrets.prod.yaml > secrets.prod.enc.yaml

# Im Deployment per Kustomize einbinden
# config/meeting-automation/overlays/prod/kustomization.yaml
secretGenerator:
- name: app-secrets
  files:
  - secrets.prod.enc.yaml
  type: Opaque
```

### Option 2: Sealed Secrets (Bitnami)

```bash
# Controller installieren
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system

# Secret versiegeln
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# Versiegeltes Secret deployen
kubectl apply -f sealed-secret.yaml
# → Controller entsiegelt automatisch
```

## Environment-Separation

### Namespace-Strategie

```bash
# Namespaces erstellen
kubectl create namespace meeting-automation-dev
kubectl create namespace meeting-automation-staging
kubectl create namespace meeting-automation-prod

# ResourceQuota pro Namespace
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: dev-quota
  namespace: meeting-automation-dev
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    persistentvolumeclaims: "5"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: prod-quota
  namespace: meeting-automation-prod
spec:
  hard:
    requests.cpu: "16"
    requests.memory: 32Gi
    limits.cpu: "32"
    limits.memory: 64Gi
    persistentvolumeclaims: "20"
EOF
```

### CD-Pipeline (GitHub Actions + ArgoCD)

```yaml
# .github/workflows/deploy-prod.yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Build & Push Docker Image
      run: |
        docker build -t youruser/backend:${{ github.sha }} ./backend
        docker push youruser/backend:${{ github.sha }}
    - name: Update Kustomize Image Tag
      run: |
        cd config/meeting-automation/overlays/prod
        kustomize edit set image backend=youruser/backend:${{ github.sha }}
        git commit -am "chore: bump backend to ${{ github.sha }}"
        git push
    # ArgoCD sync automatisch (Auto-Sync ist aktiv)
    # Oder manuell:
    # argocd app sync meeting-automation-prod
```

## Validation

```bash
# ArgoCD UI
kubectl port-forward -n argocd svc/argocd-server 8080:443

# App-Status via CLI
argocd app list
argocd app get meeting-automation-prod

# Secrets prüfen (SOPS)
sops --decrypt secrets.prod.enc.yaml

# Environment-Isolation testen
kubectl get pods -n meeting-automation-dev
kubectl get pods -n meeting-automation-prod
# → Unterschiedliche Pods, getrennte Namespaces

# Sync-Status beobachten
argocd app wait meeting-automation-prod --health
```
