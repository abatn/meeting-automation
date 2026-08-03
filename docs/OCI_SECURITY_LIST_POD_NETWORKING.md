# OCI Security List — Pod-to-Pod Networking Fix

**Erstellt:** 2026-08-03  
**Status:** DOKUMENTATION (keine Modifikation)  
**Kontext:** Prometheus kann Pods nicht scrapen wegen OCI VNIC Security List

---

## 1. Problem

### Symptom
```
Prometheus → Pod-IP (10.42.0.116:8000) → "No route to host"
Prometheus → Service DNS (backend:8000) → METRICS ✅
```

### Ursache
OCI VNIC Security List blockiert Traffic von Pod-CIDR (10.42.0.0/16) zu anderen Pods.

### Beweis
| Test | Ergebnis |
|------|----------|
| Host → Pod (ping 10.42.0.53) | ✅ Funktioniert |
| Pod → Pod (selber Namespace) | ❌ "No route to host" |
| Pod → Pod (anderer Namespace) | ❌ Timeout |
| Pod → Service DNS | ✅ Funktioniert |

---

## 2. Offizielle Empfehlung

### Prometheus Documentation
> "Scrape Pod-IPs directly — scraping Service ClusterIPs only queries one load-balanced backend, causing incomplete metrics."

### ServiceMonitor Flow
```
ServiceMonitor
    ↓
Service (ClusterIP)
    ↓
Endpoints (Pod-IPs)
    ↓
Prometheus scrapes Pod-IPs direkt
```

**Fazit:** Pod-to-Pod Routing MUSS funktionieren für korrektes Monitoring.

---

## 3. Benötigte Ports

### Prometheus Scrape-Ports

| Port | Service | Namespace | Protokoll |
|------|---------|-----------|-----------|
| 8000 | backend | meeting-automation-staging | TCP |
| 8080 | kube-state-metrics, alertmanager | monitoring | TCP |
| 9090 | prometheus | monitoring | TCP |
| 9093 | alertmanager | monitoring | TCP |
| 9100 | node-exporter | monitoring | TCP |
| 9187 | CNPG exporter | meeting-automation-staging | TCP |
| 6379 | redis | meeting-automation-staging | TCP |
| 5672 | rabbitmq | meeting-automation-staging | TCP |
| 15672 | rabbitmq management | meeting-automation-staging | TCP |
| 9000 | minio | meeting-automation-staging | TCP |
| 9001 | minio console | meeting-automation-staging | TCP |
| 5432 | postgres | meeting-automation-staging | TCP |

### Additional Ports (für volle Funktionalität)

| Port | Service | Zweck |
|------|---------|-------|
| 80 | frontend, ingress-nginx | HTTP |
| 443 | ingress-nginx | HTTPS |
| 7880 | livekit-server | WebRTC |
| 7881 | livekit-server | WebRTC TCP |
| 3478 | livekit-server | STUN/TURN |
| 5678 | n8n | Web UI |

---

## 4. OCI Security List Regel

### Staging (OCI — 158.180.18.110)

**Name:** `k3s-pod-networking`  
**Direction:** Ingress + Egress  
**Source:** `10.42.0.0/16` (Pod-CIDR)  
**Destination:** `10.42.0.0/16` (Pod-CIDR)  
**Protocol:** TCP  
**Ports:** `8000, 8080, 9090, 9093, 9100, 9187, 6379, 5672, 15672, 9000, 9001, 5432, 80, 443, 7880, 7881, 5678`

### Production (Contabo — 169.58.83.32)

**Name:** `k3s-pod-networking`  
**Direction:** Ingress + Egress  
**Source:** `10.42.0.0/16` (Pod-CIDR)  
**Destination:** `10.42.0.0/16` (Pod-CIDR)  
**Protocol:** TCP  
**Ports:** `8000, 8080, 9090, 9093, 9100, 9187, 6379, 5672, 15672, 9000, 9001, 5432, 80, 443, 7880, 7881, 5678`

---

## 5. Implementierungsplan

### Schritt 1: OCI Security List (Staging)

1. OCI Console → Networking → VCN → Default Security List
2. Neue Regel hinzufügen:
   - Name: `k3s-pod-networking`
   - Direction: Ingress
   - Source: `10.42.0.0/16`
   - Protocol: TCP
   - Destination Port Range: `80,443,5432,5672,5678,6379,7880,7881,8000,8080,9000,9001,9090,9093,9100,9187,15672`
3. Gleiche Regel für Egress hinzufügen

### Schritt 2: Verifikation (Staging)

```bash
# Test 1: Pod-to-Pod
kubectl run test --image=busybox --rm -it --restart=Never -- wget -qO- --timeout=5 http://10.42.0.116:8000/metrics

# Test 2: Prometheus Targets
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# Dann: http://localhost:9090/targets prüfen
```

### Schritt 3: CI/CD Integration

**Keine CI/CD Änderung nötig** — OCI Security List ist eine manuelle Infrastruktur-Änderung.

### Schritt 4: Production (Contabo)

1. Contabo Firewall / Security Group konfigurieren
2. Gleiche Ports freigeben
3. Verifikation

---

## 6. CI/CD Staging vs Production

### Staging (OCI)

| Aspekt | Status |
|--------|--------|
| OCI Security List | ⏸️ Manuell (OCI Console) |
| Pod-CIDR | 10.42.0.0/16 |
| Node-IP | 10.0.0.191 |
| Öffentliche IP | 158.180.18.110 |

### Production (Contabo)

| Aspekt | Status |
|--------|--------|
| Firewall | ⏸️ Manuell (Contabo Panel) |
| Pod-CIDR | 10.42.0.0/16 |
| Node-IP | 10.0.0.x |
| Öffentliche IP | 169.58.83.32 |

### CI/CD Pipeline

```
Git Push → GitHub Actions → Docker Build → Deploy
                                    ↓
                        Staging (OCI) → Production (Contabo)
                                    ↓
                        OCI Security List → Contabo Firewall
                        (manuell)         (manuell)
```

**Hinweis:** Security List Änderungen sind NICHT in CI/CD automatiiert. Sie müssen manuell in der jeweiligen Cloud-Konsole durchgeführt werden.

---

## 7. HARTE LESSONS

| # | Regel |
|---|-------|
| OSL1 | **OCI VNIC Security List blockiert Pod-CIDR → Pod-CIDR Traffic** — Pods können einander nur erreichen wenn die Security List explizit Traffic zwischen 10.42.0.0/16 erlaubt. |
| OSL2 | **Service DNS funktioniert trotzdem** — kube-proxy iptables arbeitet auf Node-Level, nicht auf Pod-Level. |
| OSL3 | **Offizielle Empfehlung: Pod-IPs scrapen** — Nicht Service ClusterIPs (laut Prometheus Doku). |
| OSL4 | **Security List ist manuell** — Nicht in CI/CD automatiiert. Jede Umgebung (Staging, Production) muss separat konfiguriert werden. |
| OSL5 | **Pod-CIDR kann sich ändern** — Bei Cluster-Neustart kann der Pod-CIDR (10.42.0.0/16) anders sein. Immer prüfen: `kubectl get nodes -o jsonpath='{.items[0].spec.podCIDR}'` |

---

## 8. Zusammenfassung

| Schritt | Verantwortlich | Status |
|---------|---------------|--------|
| OCI Security List (Staging) | OCI Console (manuell) | ⏸️ Offen |
| Verifikation (Staging) | Buffy (automatisch) | ⏸️ Nach Security List |
| OCI Security List (Production) | Contabo Panel (manuell) | ⏸️ Offen |
| Verifikation (Production) | Buffy (automatisch) | ⏸️ Nach Security List |

**Nächster Schritt:** OCI Security List in Staging konfigurieren (manuell in OCI Console).
