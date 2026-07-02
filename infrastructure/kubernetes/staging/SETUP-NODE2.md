# Zweite k3s Node Setup — Meeting Automation Staging

## Cluster-Übersicht (Stand: 2026-06-28)

| | Node 1 (Server) | Node 2 (Agent) |
|---|---|---|
| Instance | instance-20260329-0846 | instance-20260628-1520 |
| IP | 10.0.0.191 | 10.0.0.11 |
| AD | AD-3 | AD-3 |
| k3s | v1.35.5+k3s1 | v1.35.5+k3s1 |
| Rolle | control-plane | agent |

## Voraussetzungen
- OCI VM: ARM64, Oracle Linux 9.7, 4 OCPUs, 24GB RAM
- Internal IP: 10.0.0.11 (im gleichen VCN/Subnetz wie Node 1)
- **Beide Nodes müssen in der gleichen Availability Domain sein** (AD-3)
- Security List: UDP 8472 (Flannel VXLAN) — **muss Protocol 17 (UDP) sein, NICHT Protocol 6 (TCP)**

## Schritt 0: firewalld konfigurieren (ISO 27001 A.8.20)

firewalld bleibt aktiv (ISO 27001 konform), aber k3s-spezifische Ports müssen geöffnet werden:

```bash
# Auf Node 2:
sudo firewall-cmd --permanent --zone=trusted --add-source=10.42.0.0/16   # Pods
sudo firewall-cmd --permanent --zone=trusted --add-source=10.43.0.0/16   # Services
sudo firewall-cmd --permanent --add-port=6443/tcp     # API Server
sudo firewall-cmd --permanent --add-port=10250/tcp    # Kubelet
sudo firewall-cmd --permanent --add-port=8472/udp     # Flannel VXLAN
sudo firewall-cmd --permanent --add-port=5001/tcp     # Spegel (optional)
sudo firewall-cmd --reload
```

## Schritt 1: k3s Agent auf Node 2 installieren

```bash
# Auf Node 2:
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION=v1.35.5+k3s1 \
  K3S_URL=https://10.0.0.191:6443 \
  K3S_TOKEN="K1026f6b1bec65e8b3777d974f649c59f1026b754840d3f388fb6b3d5d85b83b541::server:1212ffc371acb784d910963fe1cae003" \
  sh -s - agent
```

## Schritt 2: Node verifizieren (auf Node 1)

```bash
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get nodes -o wide
# Erwartet: 2 Nodes, beide Ready, beide v1.35.5+k3s1
```

## Schritt 3: Longhorn Replica-Count auf 2 setzen

```bash
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml patch settings.longhorn.io default-replica-count -n longhorn-system --type merge -p '{"value":"2"}'
```

## Schritt 4: CloudNativePG installieren

```bash
# Operator installieren
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm upgrade --install cnpg cnpg/cloudnative-pg --namespace cnpg-system --create-namespace

# PostgreSQL Cluster deployen
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml apply -f infrastructure/kubernetes/staging/cnpg-cluster.yaml
```

**Wichtig**: Das Secret `postgres-secrets` muss die Keys `username` und `password` enthalten (nicht `POSTGRES_USER`/`POSTGRES_PASSWORD`).

## Schritt 5: NetworkPolicies anwenden (ISO 27001 A.8.20)

```bash
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml apply -f infrastructure/kubernetes/staging/network-policies.yaml
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml apply -f infrastructure/kubernetes/staging/n8n-nodeport-policy.yaml
```

## Schritt 6: Velero installieren

```bash
chmod +x infrastructure/kubernetes/staging/velero-install.sh
./infrastructure/kubernetes/staging/velero-install.sh
```

## Verifikation

```bash
# Nodes
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get nodes -o wide

# Cross-node DNS Test
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml run test-dns --image=busybox --restart=Never \
  --overrides='{"spec":{"nodeName":"instance-20260628-1520"}}' \
  -- sh -c "nslookup kubernetes.default.svc.cluster.local"

# Longhorn Volumes
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get volumes.longhorn.io -n longhorn-system

# CloudNativePG Cluster
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get clusters.postgresql.cnpg.io -n meeting-automation-staging

# Velero Backups
velero backup get
velero schedule get

# NetworkPolicies
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get networkpolicies -A
```

## OCI Security List (Flannel VXLAN)

**Kritisch**: VXLAN nutzt UDP Port 8472. In der OCI Security List muss das als **Protocol 17 (UDP)** konfiguriert sein:

| Port | Protocol | Code | Zweck |
|------|----------|------|-------|
| 8472 | UDP | 17 | Flannel VXLAN |
| 6443 | TCP | 6 | Kubernetes API Server |
| 10250 | TCP | 6 | Kubelet |
| 80 | TCP | 6 | nginx-ingress HTTP |
| 443 | TCP | 6 | nginx-ingress HTTPS |
| 9000 | TCP | 6 | MinIO (Cross-node S3, hostNetwork erforderlich) |

Falsch (TCP/Protocol 6 für VXLAN) → VXLAN-Pakete werden nicht weitergeleitet → Cross-node Pod-Kommunikation funktioniert nicht.

**Hinweis zu Port 9000**: MinIO läuft mit `hostNetwork: true` auf Node 2. Cross-node Traffic (Velero auf Node 1 → MinIO auf Node 2) braucht Port 9000 in der Security List. Ohne hostNetwork would MinIO über flannel VXLAN (Port 8472) erreichbar sein.

## Rollback

Falls die zweite Node Probleme verursacht:
```bash
# Node 2 entfernen
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml delete node instance-20260628-1520

# Longhorn zurück auf 1 Replica
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml patch settings.longhorn.io default-replica-count -n longhorn-system --type merge -p '{"value":"1"}'

# k3s-agent auf Node 2 stoppen und deinstallieren
sudo systemctl stop k3s-agent
sudo /usr/local/bin/k3s-agent-uninstall.sh
```

## Bekannte Probleme

1. **ipset/iptables-nft Inkompatibilität**: Auf Oracle Linux 9.7 mit iptables-nft Backend zeigt `iptables -L KUBE-POD-FW-*` den Fehler "Incompatible with this kernel". Das ist ein Display-Problem — kube-router funktioniert trotzdem korrekt.

2. **CNPG Secret Key-Mismatch**: Das `postgres-secrets` Secret enthält `POSTGRES_USER`/`POSTGRES_PASSWORD`, aber CloudNativePG erwartet `username`/`password`. Muss vor dem Deploy des Clusters gefixt werden.
