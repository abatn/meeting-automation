# cert-manager Installation — Production (169.58.83.32)

**Stand:** 2026-07-31
**Server:** Contabo VPS, 169.58.83.32
**Domain:** meeting-automate.tn (via Cloudflare DNS)
**Cluster:** k3s v1.36.2+k3s1
**Namespace:** meeting-automation (NICHT meeting-automation-staging!)

---

## Status Quo (VORHER)

| Komponente | Status |
|-----------|--------|
| nginx-ingress | ✅ Running (LoadBalancer, External IP: 169.58.83.32) |
| Ingress `meeting-production` | ✅ Vorhanden (meeting-automate.tn, ingressClassName: nginx) |
| cert-manager | ❌ NICHT installiert |
| TLS Zertifikat | ❌ Kein Zertifikat (kein `staging-tls` Secret) |
| Ports 80/443 | ✅ Offen (nginx-ingress LoadBalancer) |
| Cloudflare | ✅ DNS + Proxy aktiv |

---

## Lernpunkte aus Staging

| Lesson | Detail |
|--------|--------|
| **K10: hostNetwork NICHT hostPort** | Auf OCI VMs: `hostNetwork: true` + `dnsPolicy: ClusterFirstWithHostNet`. Auf Contabo mit LoadBalancer: NICHT nötig (LoadBalancer funktioniert). |
| **K11: cert-manager braucht NetworkPolicy** | `default-deny-all` blockiert ACME Solver Pods. NetworkPolicy für Solver erstellen. |
| **K12: ACME Solver braucht Port 80** | Solver Pod muss von ingress-nginx erreichbar sein (Port 80). |
| **K13: Helm values korrekt** | `controller.service.type=LoadBalancer`, `externalTrafficPolicy: Local`. |

---

## Schritt-für-Schritt Anleitung

### Schritt 1: cert-manager installieren

```bash
# Auf Production (169.58.83.32):
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# CRDs installieren
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.crds.yaml

# cert-manager per Helm installieren
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.15.0 \
  --set crds.enabled=true \
  --wait --timeout 120s

# Verifizieren: 3/3 Pods Running
kubectl get pods -n cert-manager
# Erwartung:
# cert-manager-xxxxx                 1/1  Running
# cert-manager-cainjector-xxxxx      1/1  Running
# cert-manager-webhook-xxxxx         1/1  Running
```

### Schritt 2: ClusterIssuer für Let's Encrypt erstellen

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@meeting.tn
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Verifizieren
kubectl get clusterissuer letsencrypt-prod -o jsonpath='{.status.conditions[0].status}'
# Erwartung: True
```

### Schritt 3: Ingress mit TLS Annotation patchen

**WICHTIG:** Der bestehende Ingress `meeting-production` braucht die cert-manager Annotation + TLS Block.

```bash
# Aktuellen Ingress patchen
kubectl patch ingress meeting-production -n meeting-automation --type='json' -p='[
  {"op": "add", "path": "/metadata/annotations/cert-manager.io~1cluster-issuer", "value": "letsencrypt-prod"},
  {"op": "add", "path": "/spec/tls", "value": [{"hosts": ["meeting-automate.tn"], "secretName": "production-tls"}]}
]'

# Verifizieren
kubectl get ingress meeting-production -n meeting-automation -o jsonpath='{.metadata.annotations}' | python3 -m json.tool
kubectl get ingress meeting-production -n meeting-automation -o jsonpath='{.spec.tls}'
```

**Falls der Ingress noch keinen TLS Block hat:**

```bash
# Vollständiges Ingress-Patch (nur wenn obiger Befehl fehlschlägt)
kubectl patch ingress meeting-production -n meeting-automation --type='merge' -p '{
  "metadata": {
    "annotations": {
      "cert-manager.io/cluster-issuer": "letsencrypt-prod"
    }
  },
  "spec": {
    "tls": [{
      "hosts": ["meeting-automate.tn"],
      "secretName": "production-tls"
    }]
  }
}'
```

### Schritt 4: NetworkPolicy für ACME Solver

**Hintergrund:** Production hat KEINE `default-deny-all` NetworkPolicy (anders als Staging). Trotzdem ist es gut, die Policy zu haben für den Fall, dass später eine hinzugefügt wird.

```bash
# Prüfen ob default-deny-all existiert
kubectl get networkpolicy -n meeting-automation

# Falls ja: ACME Solver Policy erstellen
cat <<'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: acme-solver-allow-ingress
  namespace: meeting-automation
spec:
  podSelector:
    matchLabels:
      acme.cert-manager.io/http01-solver: "true"
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8089
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: cert-manager
    ports:
    - protocol: TCP
      port: 8089
EOF

# Plus breitere Policy für alle Pods
cat <<'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ingress-nginx-allow
  namespace: meeting-automation
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 8089
    - protocol: TCP
      port: 8000
    - protocol: TCP
      port: 5678
    - protocol: TCP
      port: 7880
EOF
```

### Schritt 5: Warten und Verifizieren

```bash
# Challenge beobachten (max 5 Min)
kubectl get challenge -n meeting-automation -w

# Certificate Status prüfen
kubectl get certificate -n meeting-automation
# Erwartung: READY: True nach ~2 Min

# TLS Secret prüfen
kubectl get secret production-tls -n meeting-automation
kubectl get secret production-tls -n meeting-automation -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject -issuer -dates

# Externer Test
curl -sI https://meeting-automate.tn/ 2>&1 | head -5
# Erwartung: HTTP/2 200, strict-transport-security Header

openssl s_client -connect meeting-automate.tn:443 -servername meeting-automate.tn < /dev/null 2>&1 | grep -E 'subject=|issuer=|Verify'
# Erwartung: subject=CN=meeting-automate.tn, issuer=Let's Encrypt, Verify=0 (ok)
```

---

## Cloudflare Besonderheiten

**WICHTIG:** Wenn Cloudflare als Proxy (orange Wolke) aktiv ist:

1. **SSL/TLS Modus:** Muss auf **Full (Strict)** stehen (nicht Flexible!)
   - Cloudflare Dashboard → SSL/TLS → Overview → Full (Strict)
   - Sonst: Cloudflare terminated TLS → kein Let's Encrypt Zertifikat nötig → aber unsicher

2. **Origin Server:** Muss auf `169.58.83.32` zeigen (kein CDN davor)

3. **HSTS:** Kann über Cloudflare oder nginx-ingress gesetzt werden

---

## Troubleshooting

### Challenge bleibt `pending`
```bash
# Solver Pod prüfen
kubectl get pods -n meeting-automation -l acme.cert-manager.io/http01-solver=true
kubectl logs -n meeting-automation -l acme.cert-manager.io/http01-solver=true

# Solver Service prüfen
kubectl get svc -n meeting-automation | grep cm-

# Solver Ingress prüfen
kubectl get ingress -n meeting-automation | grep cm-
```

### cert-manager Logs
```bash
kubectl logs -n cert-manager -l app.kubernetes.io/name=cert-manager --tail=50
kubectl logs -n cert-manager -l app.kubernetes.io/name=cainjector --tail=20
```

### Challenge fehlgeschlagen (5 Min Timeout)
```bash
# Challenge löschen und neu auslösen
kubectl delete challenge --all -n meeting-automation
# cert-manager erstellt automatisch neuen Challenge
```

---

## Verifikation (Checkliste)

| # | Check | Erwartung |
|---|-------|-----------|
| 1 | `kubectl get certificate -n meeting-automation` | READY: True |
| 2 | `kubectl get secret production-tls` | Existiert, 2 Keys (tls.crt, tls.key) |
| 3 | `openssl s_client` | issuer=Let's Encrypt, Verify=0 |
| 4 | `curl -sI https://meeting-automate.tn/` | HTTP/2 200, HSTS Header |
| 5 | `curl -sI http://meeting-automate.tn/` | 308 Redirect auf HTTPS |
| 6 | Frontend lädt | React App HTML (nicht 404/502) |
| 7 | Login funktioniert | /login lädt, Formular sichtbar |
| 8 | API erreichbar | /api/v1/auth/me antwortet (401 = korrekt) |
