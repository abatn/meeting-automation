# Monitoring NetworkPolicy Analyse

**Erstellt:** 2026-08-03  
**Status:** IMPLEMENTIERT (Commit `cd9eb9ec`)  
**Kontext:** Prometheus kann 13 von 15 Targets nicht scrapen

---

## 1. Aktueller Stand

### NetworkPolicies in `meeting-automation-staging`

| Policy | Schützt | Erlaubt Ingress von |
|--------|---------|---------------------|
| `default-deny-all` | Alle Pods | NICHTS (Blockiert alles) |
| `backend-policy` | backend | frontend, livekit, onlyoffice, n8n |
| `cnpg-policy` | postgres | backend, n8n, celery-worker, celery-worker-pro, celery-beat |
| `redis-policy` | redis | backend, celery-worker, celery-worker-pro, celery-beat, livekit |
| `rabbitmq-policy` | rabbitmq | backend, celery-worker, celery-worker-pro, celery-beat |
| `frontend-policy` | frontend | ingress-nginx |
| `minio-policy` | minio | backend, celery-worker, celery-worker-pro, frontend, cnpg |
| `n8n-policy` | n8n | ingress-nginx, backend |
| `onlyoffice-policy` | onlyoffice | backend, frontend |
| `livekit-policy` | livekit-server | ingress-nginx, frontend, livekit-egress, backend |
| `livekit-egress-policy` | livekit-egress | livekit-server |

### NetworkPolicies in `monitoring`

**KEINE** — es gibt keine NetworkPolicies im monitoring Namespace.

### Prometheus Targets

| Target | Namespace | IP | Status | Fehler |
|--------|-----------|-----|--------|--------|
| apiserver | kube-system | 10.0.0.191:6443 | ✅ UP | — |
| prometheus | monitoring | 10.42.0.61:9090 | ✅ UP | — |
| **backend** | meeting-automation-staging | 10.42.0.41:8000 | ❌ DOWN | connection refused |
| **backend** | meeting-automation-staging | 10.42.0.42:8000 | ❌ DOWN | connection refused |
| **kube-state-metrics** | monitoring | 10.42.0.53:8080 | ❌ DOWN | no route to host |
| **grafana** | monitoring | 10.42.0.57:3000 | ❌ DOWN | no route to host |
| **alertmanager** | monitoring | 10.42.0.60:9093 | ❌ DOWN | no route to host |
| **node-exporter** | monitoring | 10.0.0.191:9100 | ❌ DOWN | no route to host |
| **kubelet** | kube-system | 10.0.0.191:10250 | ❌ DOWN | no route to host |

---

## 2. Ursachenanalyse

### Fehler 1: `connection refused` (backend)

```
Prometheus → http://10.42.0.41:8000/metrics
    ↓
NetworkPolicy backend-policy prüft:
    Erlaubt: frontend, livekit, onlyoffice, n8n
    Prometheus: NICHT erlaubt
    ↓
Verbindung wird abgelehnt → "connection refused"
```

**Ursache:** `backend-policy` erlaubt keinen Ingress von Prometheus.

**Lösung:** Prometheus zu `backend-policy` hinzufügen.

### Fehler 2: `no route to host` (monitoring services)

```
Prometheus → http://10.42.0.53:8080/metrics (kube-state-metrics)
    ↓
Pod-IP ist nicht erreichbar → "no route to host"
```

**Ursache:** Prometheus versucht Pod-IPs direkt zu erreichen, nicht Service-IPs.

**WICHTIG:** Monitoring-namespace hat **KEINE** NetworkPolicies. Das bedeutet: "no route to host" ist **KEIN NetworkPolicy-Problem**. Es ist ein Netzwerk-Routing-Problem (CNI, kube-proxy, iptables).

---

## 3. Lösungsplan

### Schritte 1-6: Backend-Policies erweitern (IMPLEMENTIERT)

| # | Policy | Datei | Änderung |
|---|--------|-------|----------|
| 1 | backend-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |
| 2 | cnpg-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |
| 3 | redis-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |
| 4 | rabbitmq-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |
| 5 | minio-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |
| 6 | postgres-policy | network-policies.yaml | `namespaceSelector + podSelector` für Prometheus |

**Ergebnis:** ✅ Alle 6 Policies angewendet (Commit `cd9eb9ec`).

### Schritte 7-8: Monitoring-Services (unsicher)

| # | Aktion | Risiko |
|---|--------|--------|
| 7 | ServiceMonitor Namespace-Selector korrigieren | ⚠️ Unbekannt |
| 8 | NetworkPolicy für Prometheus Egress | ❌ Nicht nötig (kein default-deny) |

**Empfehlung:** Schritte 7-8 NICHT implementieren bis "no route to host" Ursache verstanden ist.

---

## 4. Verifizierte Fakten

| Fakt | Quelle | Status |
|------|--------|--------|
| Prometheus Pod Label: `app.kubernetes.io/name=prometheus` | kubectl get pod --show-labels | ✅ Verifiziert |
| NetworkPolicies in monitoring: KEINE | kubectl get networkpolicy -n monitoring | ✅ Verifiziert |
| backend-policy fehlt Prometheus | network-policies.yaml | ✅ Verifiziert |
| "no route to host" ≠ NetworkPolicy | Keine Policies in monitoring | ✅ Verifiziert |

---

## 5. Offene Fragen

| Frage | Option A | Option B |
|-------|----------|----------|
| Soll Prometheus auf alle Services zugreifen? | Ja (komplett überwachen) | Nur kritische Services |
| Soll die NetworkPolicy in Git versioniert werden? | Ja (CI/CD-kompatibel) | Nur live |
| Wie fixen wir "no route to host"? | Netzwerk-Routing analysieren |暂时 ignorieren |

---

## 6. Zusammenfassung

| Teil | Status | Ergebnis |
|------|--------|----------|
| Backend "connection refused" fixen | ✅ IMPLEMENTIERT | 6 Policies mit `namespaceSelector + podSelector` |
| Monitoring "no route to host" fixen | ⏸️ Offen | Separat analysieren |
| Egress-Policy für Prometheus | ❌ Nicht nötig | Kein default-deny in monitoring |

## 7. HARTE LESSONS

| # | Regel |
|---|-------|
| M5 | **NetworkPolicy `podSelector` ist namespace-scoped** — Kann nur Pods im selben Namespace matchen. Für Cross-Namespace: `namespaceSelector` + `podSelector` in einem `from`-Eintrag kombinieren. |
| M6 | **Immer prüfen ob der Target-Pod im selben Namespace ist** — Prometheus (monitoring) → Backend (meeting-automation-staging) = Cross-Namespace. |

**Commits:**
| Hash | Beschreibung |
|------|-------------|
| `d95e5830` | docs: Phase 195 — Analyse |
| `cd9eb9ec` | fix: namespaceSelector für Cross-Namespace NetworkPolicy |
