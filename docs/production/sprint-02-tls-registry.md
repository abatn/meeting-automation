# Sprint 2: TLS + Image Registry

> **Dauer:** ~1 Woche | **Status:** ⬜ Offen
> **Komponenten:** cert-manager (CNCF), Let's Encrypt, Docker Hub / Harbor (CNCF)

## TLS mit cert-manager

### Installation

```bash
# cert-manager installieren
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.yaml

# Prüfen
kubectl get pods -n cert-manager
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
    email: admin@meeting.tn
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: traefik
```

### Ingress mit TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: meeting-automation-ingress
  namespace: meeting-automation
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: traefik
  tls:
  - hosts:
    - app.meeting.tn
    secretName: meeting-tls
  rules:
  - host: app.meeting.tn
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

### Validation

```bash
# Zertifikats-Status prüfen
kubectl get certificate -n meeting-automation
kubectl describe certificate meeting-tls -n meeting-automation

# TLS testen
curl -vI https://app.meeting.tn
```

## Image Registry

### Option 1: Docker Hub (kostenlos)

```bash
# Login
docker login

# Taggen & Pushen
docker tag meeting-automation-backend:latest youruser/meeting-automation-backend:latest
docker tag meeting-automation-frontend:latest youruser/meeting-automation-frontend:latest
docker push youruser/meeting-automation-backend:latest
docker push youruser/meeting-automation-frontend:latest

# Im Deployment verwenden
# image: youruser/meeting-automation-backend:latest
# imagePullPolicy: Always
```

### Option 2: Harbor (CNCF, self-hosted)

```bash
# Harbor installieren
helm repo add harbor https://helm.goharbor.io
helm upgrade --install harbor harbor/harbor \
  --namespace harbor --create-namespace \
  --set expose.type=nodePort \
  --set expose.tls.auto.commonName=harbor.meeting.tn \
  --set persistence.enabled=true

# Zugriff
kubectl port-forward -n harbor svc/harbor-portal 8080:80
# URL: http://localhost:8080
# User: admin
# Pass: kubectl get secret harbor-harbor-core -n harbor -o jsonpath='{.data.HARBOR_ADMIN_PASSWORD}' | base64 -d

# Image pushen
docker tag meeting-automation-backend:latest harbor.meeting.tn/library/backend:latest
docker push harbor.meeting.tn/library/backend:latest
```

### Option 3: Docker Registry (minimal)

```bash
# Einfacher lokaler Registry
kubectl create deployment registry --image=registry:2 -n meeting-automation
kubectl expose deployment registry --port=5000 -n meeting-automation

# Nutzung
docker tag meeting-automation-backend:latest localhost:5000/backend:latest
docker push localhost:5000/backend:latest

# ImagePullSecret für private Registry
kubectl create secret docker-registry regcred \
  --docker-server=localhost:5000 \
  --docker-username=admin \
  --docker-password=admin \
  -n meeting-automation
```

## Migration von docker save/load zu Registry

### Aktuell (setup-kubernetes.sh)

```bash
docker save meeting-automation-backend:latest | gzip > /tmp/backend.tar.gz
kind load image-archive /tmp/backend.tar.gz
```

### Ziel

```bash
# In setup-kubernetes.sh ersetzen durch:
docker pull youruser/meeting-automation-backend:latest
kind load docker-image youruser/meeting-automation-backend:latest
# Oder direkt:
kubectl set image deployment/backend backend=youruser/meeting-automation-backend:latest
```
