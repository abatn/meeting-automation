# Sprint 2: TLS + Image Registry

| Feld | Wert |
|------|------|
| **Status** | ✅ Teilweise abgeschlossen (Phase 53) |
| **Dauer** | ~1 Woche (geschätzt) |
| **Komponenten** | cert-manager v1.20.2, nginx-ingress, Let's Encrypt |

## 1. TLS mit cert-manager (Phase 53 abgeschlossen)

### Installiert

```bash
# cert-manager v1.20.2 (Helm, CRDs.enabled=true)
helm install cert-manager oci://quay.io/jetstack/charts/cert-manager \
  --version v1.20.2 \
  --set crds.enabled=true \
  -n cert-manager --create-namespace

# nginx-ingress (NodePort 30080/30443)
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30080 \
  --set controller.service.nodePorts.https=30443
```

### ClusterIssuer (Let's Encrypt)

```yaml
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
```

### Ingress mit TLS

```yaml
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
```

### Validierung

```bash
# Zertifikats-Status prüfen
kubectl get certificate -n meeting-automation-staging
kubectl describe certificate staging-tls -n meeting-automation-staging

# TLS testen (nach OCI Ports 30080/30443 geöffnet)
curl -vI https://staging.meeting-automation.com
```

### Offene Schritte

| # | Schritt | Status |
|---|---------|--------|
| 1 | OCI Security List Ports 30080/30443 öffnen | ⏳ User Action |
| 2 | DNS `staging.meeting-automation.com` → 158.180.18.110 verifizieren | ⏳ |
| 3 | Let's Encrypt Certificate verifizieren | ⏳ (nach 1+2) |
| 4 | X-Forwarded-Proto Header für Backend | ❌ Offen |
| 5 | LiveKit WSS Migration | ❌ Offen |

## 2. Image Registry (Offen — Production)

### Option 1: Docker Hub (kostenlos)

```bash
docker login
docker tag meeting-automation-backend:latest youruser/meeting-automation-backend:latest
docker push youruser/meeting-automation-backend:latest
```

### Option 2: Harbor (CNCF, self-hosted)

```bash
helm repo add harbor https://helm.goharbor.io
helm upgrade --install harbor harbor/harbor \
  --namespace harbor --create-namespace \
  --set expose.type=nodePort \
  --set persistence.enabled=true
```

### Option 3: OCI Container Registry (Oracle Cloud)

```bash
# Oracle Cloud hat integrierten Container Registry (kostenlos für OCI-Kunden)
# Kein extra Setup nötig — Images direkt aus OCI pushen
```

## 3. Migration von docker save/load zu Registry

### Aktuell (Staging)

```bash
# Images werden direkt in k3s geladen (kein Kind mehr)
# k3s pulled Images direkt aus der Registry
```

### Ziel (Production)

```bash
# In CI/CD Pipeline:
docker build -t registry.meeting-automation.com/backend:latest .
docker push registry.meeting-automation.com/backend:latest

# In K8s Deployment:
# image: registry.meeting-automation.com/backend:latest
# imagePullPolicy: Always
```
