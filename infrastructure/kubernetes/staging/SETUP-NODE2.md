# Zweite k3s Node Setup — Meeting Automation Staging

## Voraussetzungen
- OCI VM: ARM64, Oracle Linux 9.7, 4 OCPUs, 24GB RAM
- Internal IP: 10.0.0.192 (im gleichen VCN wie Node 1)
- Security List: Ports 6443 (TCP), 80 (TCP), 443 (TCP), 8472 (UDP), 10250 (TCP), 10255 (TCP)

## Schritt 1: k3s Agent auf Node 2 installieren

```bash
# Auf Node 2:
curl -sfL https://get.k3s.io | K3S_URL=https://10.0.0.191:6443 K3S_TOKEN=K1026f6b1bec65e8b3777d974f649c59f1026b754840d3f388fb6b3d5d85b83b541::4bontn.305mdu581pefoah8 sh -s - agent
```

## Schritt 2: Node verifizieren (auf Node 1)

```bash
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster get nodes
# Erwartet: 2 Nodes, beide Ready
```

## Schritt 3: Longhorn Replica-Count auf 2 setzen

```bash
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster patch settings.longhorn.io default-replica-count -n longhorn-system --type merge -p '{"value":"2"}'
```

## Schritt 4: CloudNativePG installieren

```bash
# Operator installieren
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm upgrade --install cnpg cnpg/cloudnative-pg --namespace cnpg-system --create-namespace

# PostgreSQL Cluster deployen (nach Migration von StatefulSet)
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster apply -f infrastructure/kubernetes/staging/cnpg-cluster.yaml
```

## Schritt 5: Velero installieren

```bash
chmod +x infrastructure/kubernetes/staging/velero-install.sh
./infrastructure/kubernetes/staging/velero-install.sh
```

## Verifikation

```bash
# Nodes
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster get nodes

# Longhorn Volumes
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster get volumes.longhorn.io -n longhorn-system

# CloudNativePG Cluster
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster get clusters.postgresql.cnpg.io -n meeting-automation-staging

# Velero Backups
velero backup get
velero schedule get
```

## Rollback

Falls die zweite Node Probleme verursacht:
```bash
# Node 2 entfernen
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster delete node <node2-name>

# Longhorn zurück auf 1 Replica
KUBECONFIG=~/.kube/config-staging kubectl --context=staging-cluster patch settings.longhorn.io default-replica-count -n longhorn-system --type merge -p '{"value":"1"}'
```
