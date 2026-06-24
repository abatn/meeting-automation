# PROMPT: Phase 53 — k3s Endpoint Fix + cert-manager + Ingress

## KONTEXT

Dieses Projekt ist eine Meeting-Automation Platform auf einem single-node k3s Cluster (v1.35.5+k3s1) auf einer OCI VM (4 CPU, 22GB RAM, ARM64, Oracle Linux 9.7). Die Anwendung läuft im Namespace `meeting-automation-staging` mit 19 Pods (18 Running + 1 cert-manager CrashLoopBackOff).

**WICHTIG**: Wir arbeiten mit **k3s** (nicht Standard Kubernetes). Alle Lösungen müssen k3s-spezifisch sein.

## AKTUELLER STATUS

- **Cluster**: k3s v1.35.5+k3s1, single-node
- **Node**: `instance-20260329-0846`, INTERNAL-IP: `10.0.0.191`, EXTERNAL-IP: `158.180.18.110`
- **Namespace**: `meeting-automation-staging`
- **k3s Config**: `/etc/rancher/k3s/config.yaml` — hat nur `node-external-ip: 158.180.18.110`, KEIN `node-ip`
- **Kubeconfig**: `~/.kube/config-staging`, Context: `staging-cluster`
- **Domain**: `staging.meeting-automation.com` (Cloudflare DNS → 158.180.18.110)
- **Backend**: healthy, NodePort 32222
- **Frontend**: HTTP 200, NodePort 31362
- **n8n**: UI erreichbar, NodePort 31678, 7 Workflows aktiv
- **PostgreSQL**: healthy, 14 meetings, Alembic Head: `n2o3p4q5r6s7`
- **RabbitMQ**: running, probe timeout instabil (1s → 5s nötig)
- **cert-manager**: Helm v1.15.0 STATUS: `failed`. cainjector CrashLoopBackOff. Kein CA Secret.

## PROBLEME (P1-P8)

| # | Problem | Priorität | Status |
|---|---------|-----------|--------|
| P1 | cert-manager kaputt (v1.15.0, Helm failed) | Hoch | BLOCKIERT auf P2 |
| P2 | k3s Endpoint zeigt auf externe IP (158.180.18.110 statt 10.0.0.191) | KRITISCH | PLAN BEREIT |
| P3 | Disk Space 92% voll (168G/183G) | KRITISCH | ✅ BEHOBEN (Phase 52) |
| P4 | ConfigMap URLs falsch (staging.meeting-automate.tn) | Hoch | Offen |
| P5 | Kein Ingress Controller installiert | Hoch | Offen |
| P6 | 3 Traefik YAML Dateien nicht funktional | Mittel | Offen |
| P7 | RabbitMQ Readiness Probe instabil (timeout 1s) | Niedrig | Offen |
| P8 | Duplicate Secrets (minio/redis) | Niedrig | Optional |

## ROOT CAUSE (P2 — VERIFIZIERT)

k3s ohne `node-ip` nutzt die externe IP für:
1. Kubernetes API Endpoint: `kubectl get endpoints kubernetes` → `158.180.18.110:6443`
2. k3s Agent Proxy: `wss://158.180.18.110:6443/v1-k3s/connect` (timeout)

OCI Security List blockiert Port 6443 auf der Public IP. → Interner Cluster-Traffic über `10.43.0.1:443` DNATet auf `158.180.18.110:6443` → defekt.

**Beweis**:
- `curl -sk https://10.0.0.191:6443/version` → 401 (funktioniert) ✅
- `curl -sk https://158.180.18.110:6443/version` → timeout (defekt) ❌

## EXECUTION PLAN

### Step 1: P2 — k3s node-ip Fix

```bash
# 1a. node-ip zur k3s Config hinzufügen
sudo tee -a /etc/rancher/k3s/config.yaml << 'EOF'
node-ip: 10.0.0.191
EOF

# 1b. k3s neustarten
sudo systemctl restart k3s

# 1c. Verifizieren
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get endpoints kubernetes -o yaml
# Erwartung: subsets[0].addresses[0].ip = 10.0.0.191

kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get nodes -o wide
# Erwartung: INTERNAL-IP = 10.0.0.191
```

**⚠️ WICHTIG**: k3s Restart dauert 30-60s. Alle Pods starten neu. Backend muss danach nochmals健康 sein.

### Step 2: P1 — cert-manager Fresh Install

```bash
# 2a. Altes cert-manager deinstallieren
helm uninstall cert-manager -n cert-manager --kubeconfig ~/.kube/config-staging 2>/dev/null || true

# 2b. CRDs löschen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster delete crd certificaterequests.cert-manager.io certificates.cert-manager.io challenges.acme.orders.acme issuers.cert-manager.io clusterissuers.cert-manager.io cert-managerconfigs.cert-manager.io 2>/dev/null || true

# 2c. Namespace + orphaned Leases löschen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster delete namespace cert-manager --ignore-not-found
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster delete leases -n kube-system -l app=cert-manager 2>/dev/null || true

# 2d. Fresh Install mit Helm
helm install cert-manager oci://quay.io/jetstack/charts/cert-manager \
  --version v1.20.2 \
  --set crds.enabled=true \
  -n cert-manager --create-namespace \
  --kubeconfig ~/.kube/config-staging

# 2e. Verifizieren (3/3 pods Running)
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get pods -n cert-manager -w
# Erwartung: cert-manager, cert-manager-cainjector, cert-manager-webhook alle Running

# 2f. CA Secret prüfen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get secret -n cert-manager
# Erwartung: cert-manager-ca Secret vorhanden
```

### Step 3: P5 — nginx-ingress Install

```bash
# 3a. Helm Repo hinzufügen
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# 3b. Installieren
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30080 \
  --set controller.service.nodePorts.https=30443 \
  --kubeconfig ~/.kube/config-staging

# 3c. Verifizieren
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get pods -n ingress-nginx
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get svc -n ingress-nginx
```

### Step 4: P4 — ConfigMap URLs korrigieren

```bash
# 4a. Aktuelle ConfigMap prüfen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get configmap backend-config -n meeting-automation-staging -o yaml

# 4b. URLs patchen (6 keys):
# LIVEKIT_PUBLIC_URL, FRONTEND_URL, ALLOWED_ORIGINS, NEXTAUTH_URL, PUBLIC_DOMAIN
# staging.meeting-automate.tn → staging.meeting-automation.com
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster patch configmap backend-config -n meeting-automation-staging --type merge -p '{"data":{"LIVEKIT_PUBLIC_URL":"wss://staging.meeting-automation.com","FRONTEND_URL":"https://staging.meeting-automation.com","ALLOWED_ORIGINS":"https://staging.meeting-automation.com","NEXTAUTH_URL":"https://staging.meeting-automation.com","PUBLIC_DOMAIN":"staging.meeting-automation.com"}}'

# 4c. Backend Pods neustarten
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster rollout restart deployment/backend -n meeting-automation-staging
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster rollout status deployment/backend -n meeting-automation-staging --timeout=120s
```

### Step 5: ClusterIssuer + Ingress erstellen

```bash
# 5a. ClusterIssuer (Let's Encrypt HTTP-01)
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster apply -f - << 'EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@meeting-automation.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# 5b. Ingress erstellen (Backend + Frontend)
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster apply -f - << 'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: staging-ingress
  namespace: meeting-automation-staging
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - staging.meeting-automation.com
    secretName: staging-tls
  rules:
  - host: staging.meeting-automation.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
EOF

# 5c. Verifizieren
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get ingress -n meeting-automation-staging
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get certificate -n meeting-automation-staging
```

### Step 6: P7 — RabbitMQ Probe Timeout Fix

```bash
# 6a. RabbitMQ Deployment patchen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster patch deployment rabbitmq-staging -n meeting-automation-staging --type json -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/timeoutSeconds", "value": 5}, {"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/timeoutSeconds", "value": 5}]'
```

### Step 7: P6 — Traefik Dateien löschen

```bash
# 7a. Nicht-funktionale Traefik Dateien löschen
rm -f infrastructure/kubernetes/staging/traefik-ingressroute.yaml
rm -f infrastructure/kubernetes/staging/traefik-ingressroute-local.yaml
rm -f infrastructure/kubernetes/staging/traefik-middlewares.yaml
```

### Step 8: Verifikation

```bash
# 8a. Alle Pods prüfen
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get pods -A

# 8b. Backend Health
curl -s http://158.180.18.110:32222/health

# 8c. Frontend
curl -s -o /dev/null -w "%{http_code}" http://158.180.18.110:31362/

# 8d. cert-manager
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get pods -n cert-manager

# 8e. Ingress
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get ingress -n meeting-automation-staging

# 8f. Certificate
kubectl --kubeconfig ~/.kube/config-staging --context staging-cluster get certificate -n meeting-automation-staging
```

## REGELN

1. **NICHT raten** — Nur verifizierte Fakten verwenden
2. **k3s-spezifisch** — Keine Standard-K8s Annahmen
3. **Vor Änderung prüfen** — Immer aktuellen Zustand verifizieren
4. **Alle Pods müssen Running sein** nach jedem Step
5. **Backend Health Check** nach jedem k3s Restart
6. **.loop.md updaten** nach jedem abgeschlossenen Step

## WICHTIGE DATEIEN

| Datei | Zweck |
|-------|-------|
| `/home/opc/meeting-automation/.loop.md` | Master Tracking — Phase 52 + P1-P8 |
| `/etc/rancher/k3s/config.yaml` | k3s Config — BENÖTIGT `node-ip: 10.0.0.191` |
| `~/.kube/config-staging` | Kubeconfig, Context: `staging-cluster` |
| `infrastructure/kubernetes/staging/backend-config.yaml` | 6 URLs müssen geändert werden |
| `infrastructure/kubernetes/staging/rabbitmq-secrets.yaml` | Probe timeout Fix |

## OCI FIREWALL (User Action nötig)

Für nginx-ingress müssen Ports in OCI Security List geöffnet werden:
- **Port 30080** (TCP ingress) — HTTP
- **Port 30443** (TCP ingress) — HTTPS

## NACHFOLGENDE PHASEN

Nach Phase 53:
- Phase 54: TLS Certificate Verifikation (Let's Encrypt)
- Phase 55: LiveKit WSS Migration (wss:// bei HTTPS)
- Phase 56: Production Deployment (Sprint 5)
