# Autoscaling Architektur — KEDA statt Hardcoded HPA

**Erstellt:** 2026-08-14
**Status:** Plan (nicht implementiert)
**Ziel:** Keine Hardcoded Limits, dynamisches Scaling basierend auf Last

---

## 1. Problem: Hardcoded HPA

### Aktueller Stand

```yaml
# celery-worker-hpa.yaml (AKTUELL — schlecht):
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 1    # ← Hardcoded
  maxReplicas: 4    # ← Hardcoded
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 80
```

### Probleme

| Problem | Impact |
|---------|--------|
| **minReplicas: 1** | Worker läuft immer, auch wenn Queue leer (Ressourcenverschwendung) |
| **maxReplicas: 4** | Bei 10 Messages nur 4 Workers (Wartezeit) |
| **CPU als Trigger** | CPU steigt erst NACHDEM Tasks laufen (zu spät) |
| **Kein Queue-Awareness** | HPA weiß nicht ob Tasks warten |
| **Kein Scale-to-Zero** | Immer mindestens 1 Pod (Kosten) |

---

## 2. Lösung: KEDA (Kubernetes Event-driven Autoscaling)

### Was ist KEDA?

KEDA ist ein Kubernetes Operator, der:
- **Event-basiert** skaliert (nicht CPU-basiert)
- **Queue-Depth** als Trigger nutzt (RabbitMQ, Kafka, etc.)
- **Scale-to-Zero** unterstützt (kein Pod wenn keine Tasks)
- **Multi-Trigger** unterstützt (CPU + Queue + Custom Metrics)

### Wie funktioniert es?

```
RabbitMQ Queue: transcription_gratuit
  │
  ├─ 0 Messages → KEDA skaliert auf 0 Pods
  │
  ├─ 5 Messages → KEDA skaliert auf 1 Pod
  │
  ├─ 10 Messages → KEDA skaliert auf 2 Pods
  │
  └─ 50 Messages → KEDA skaliert auf 10 Pods (max)
```

---

## 3. KEDA ScaledObjects (alle Services)

### 3.1 Celery Workers (GRATUIT)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-gratuit
spec:
  scaleTargetRef:
    name: celery-worker-staging
  minReplicaCount: 0        # Scale-to-zero
  maxReplicaCount: 10       # Dynamisch
  triggers:
    - type: rabbitmq
      metadata:
        queueName: transcription_gratuit
        queueLength: "5"     # 5 Messages pro Worker
```

**Verhalten:**
- 0 Messages → 0 Pods (keine Ressourcenverschwendung)
- 5 Messages → 1 Pod
- 10 Messages → 2 Pods
- 50 Messages → 10 Pods

### 3.2 Celery Workers (PRO)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-pro
spec:
  scaleTargetRef:
    name: celery-worker-pro-staging
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
    - type: rabbitmq
      metadata:
        queueName: transcription_pro
        queueLength: "5"
```

**Verhalten:** Identisch zu GRATUIT, aber für PRO Queue.

### 3.3 LiveKit Egress

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: livekit-egress
spec:
  scaleTargetRef:
    name: livekit-egress
  minReplicaCount: 1        # Mindestens 1 (Recording immer möglich)
  maxReplicaCount: 5
  triggers:
    - type: cpu
      metricType: Utilization
      metadata:
        value: "80"
```

**Verhalten:**
- CPU < 80% → 1 Pod
- CPU > 80% → 2-5 Pods (parallele Recordings!)

### 3.4 Backend

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: backend
spec:
  scaleTargetRef:
    name: backend
  minReplicaCount: 2        # HA (mindestens 2)
  maxReplicaCount: 10
  triggers:
    - type: cpu
      metricType: Utilization
      metadata:
        value: "70"
```

**Verhalten:**
- CPU < 70% → 2 Pods (HA)
- CPU > 70% → 3-10 Pods

---

## 4. Vergleich: Hardcoded HPA vs. KEDA

| Eigenschaft | Hardcoded HPA | KEDA |
|-------------|---------------|------|
| **Min Replicas** | Hardcoded (1) | Dynamisch (0-2) |
| **Max Replicas** | Hardcoded (4) | Dynamisch (5-10) |
| **Trigger** | CPU (nicht Queue) | Queue-Depth + CPU |
| **Scale-to-Zero** | ❌ Nein | ✅ Ja |
| **Queue-aware** | ❌ Nein | ✅ Ja |
| **Multi-Tenant** | ❌ Nein | ✅ Ja (pro Queue) |
| **Reaktionszeit** | Langsam (CPU steigt spät) | Schnell (Queue sofort) |
| **Ressourcen** | Immer Pods laufen | Nur bei Bedarf |

---

## 5. Multi-Tenant Verhalten

### Fall 1: 1 GRATUIT Tenant aktiv

```
Queue: transcription_gratuit = 3 Messages
  → KEDA skaliert GRATUIT Workers auf 1 Pod
  → PRO Workers: 0 Pods (keine Messages)
  → Egress: 1 Pod (kein Recording)
```

### Fall 2: 3 Tenants gleichzeitig (1 PRO + 2 GRATUIT)

```
Queue: transcription_gratuit = 8 Messages
  → KEDA skaliert GRATUIT Workers auf 2 Pods
Queue: transcription_pro = 5 Messages
  → KEDA skaliert PRO Workers auf 1 Pod
  → Egress: 1 Pod (CPU < 80%)
```

### Fall 3: 10 Tenants gleichzeitig (Burst)

```
Queue: transcription_gratuit = 30 Messages
  → KEDA skaliert GRATUIT Workers auf 6 Pods
Queue: transcription_pro = 20 Messages
  → KEDA skaliert PRO Workers auf 4 Pods
  → Egress: 3 Pods (CPU > 80%)
  → Backend: 5 Pods (CPU > 70%)
```

---

## 6. Implementierungs-Schritte

### Schritt 1: KEDA installieren

```bash
helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --wait --timeout 5m
```

### Schritt 2: Hardcoded HPA entfernen

```bash
kubectl delete hpa celery-worker-hpa -n meeting-automation-staging
```

### Schritt 3: KEDA ScaledObjects erstellen

```bash
kubectl apply -f infrastructure/kubernetes/staging/keda-scaledobjects.yaml
```

### Schritt 4: Verifikation

```bash
# KEDA ScaledObjects prüfen
kubectl get scaledobject -n meeting-automation-staging

# KEDA Logs prüfen
kubectl logs -n keda -l app.kubernetes.io/name=keda-operator --tail=20
```

---

## 7. Monitoring

### KEDA Metrics

```bash
# KEDA Operator Metrics
kubectl port-forward -n keda svc/keda-metrics-server 8080:8080

# Aktive ScaledObjects
kubectl get scaledobject -n meeting-automation-staging -o custom-columns='NAME:.metadata.name,TARGET:.spec.scaleTargetRef.name,MIN:.spec.minReplicaCount,MAX:.spec.maxReplicaCount,REPLICAS:.status.currentScale'
```

### Prometheus Alerts

```yaml
# KEDA Scaling Events
- alert: KEDAScalingUp
  expr: keda_scaledobject_current_replicas > keda_scaledobject_min_replicas
  for: 5m
  annotations:
    summary: "KEDA skaliert {{ $labels.name }} hoch"

- alert: KEDAScalingDown
  expr: keda_scaledobject_current_replicas == 0
  for: 10m
  annotations:
    summary: "KEDA hat {{ $labels.name }} auf 0 skaliert"
```

---

## 8. CI/CD Integration

### 8.1 Staging Deploy (automatisch via CI)

```yaml
# .github/workflows/deploy-staging.yml
steps:
  - name: KEDA installieren (idempotent)
    run: |
      helm upgrade --install keda kedacore/keda \
        --namespace keda --create-namespace \
        --set operator.replicaCount=1 \
        --set metricsServer.replicaCount=1 \
        --wait --timeout 5m

  - name: KEDA ScaledObjects deployen
    run: |
      kubectl apply -f infrastructure/kubernetes/staging/keda-scaledobjects.yaml

  - name: Hardcoded HPA entfernen
    run: |
      kubectl delete hpa celery-worker-hpa -n meeting-automation-staging --ignore-not-found

  - name: LiveKit Egress hostNetwork entfernen (fuer parallele Recordings)
    run: |
      kubectl patch deployment livekit-egress -n meeting-automation-staging \
        --type='json' \
        -p='[{"op":"replace","path":"/spec/template/spec/hostNetwork","value":false},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirst"}]'

  - name: Verifikation
    run: |
      kubectl get scaledobject -n meeting-automation-staging
      kubectl get pods -n keda
```

### 8.2 Production Deploy (nach Staging-Test)

```yaml
# .github/workflows/deploy-production.yml
steps:
  - name: KEDA installieren (idempotent)
    run: |
      helm upgrade --install keda kedacore/keda \
        --namespace keda --create-namespace \
        --set operator.replicaCount=1 \
        --set metricsServer.replicaCount=1 \
        --wait --timeout 5m

  - name: KEDA ScaledObjects deployen
    run: |
      kubectl apply -f infrastructure/kubernetes/production/keda-scaledobjects.yaml

  - name: Hardcoded HPA entfernen
    run: |
      kubectl delete hpa celery-worker-hpa -n meeting-automation --ignore-not-found

  - name: LiveKit Egress hostNetwork entfernen
    run: |
      kubectl patch deployment livekit-egress -n meeting-automation \
        --type='json' \
        -p='[{"op":"replace","path":"/spec/template/spec/hostNetwork","value":false},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirst"}]'

  - name: Verifikation
    run: |
      kubectl get scaledobject -n meeting-automation
      kubectl get pods -n keda
```

### 8.3 Reihenfolge (Kritisch!)

```
1. KEDA installieren (Helm)
2. KEDA ScaledObjects deployen
3. Hardcoded HPA entfernen
4. LiveKit Egress hostNetwork entfernen
5. Verifikation (ScaledObjects, Pods, Logs)
```

**Warum diese Reihenfolge?**
- KEDA MUSS zuerst installiert sein (sonst gibt es keine ScaledObjects)
- ScaledObjects MÜSSEN vor HPA-Entfernung deployt sein (sonst keine Pods)
- hostNetwork-Entfernung ist der letzte Schritt (Riskanteste Änderung)

### 8.4 Rollback (bei Problemen)

```bash
# 1. Hardcoded HPA wiederherstellen
kubectl apply -f infrastructure/kubernetes/staging/celery-worker-hpa.yaml

# 2. KEDA ScaledObjects entfernen
kubectl delete scaledobject -n meeting-automation-staging --all

# 3. LiveKit Egress hostNetwork wiederherstellen
kubectl patch deployment livekit-egress -n meeting-automation-staging \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'

# 4. KEDA deinstallieren (optional)
helm uninstall keda -n keda
```

### 8.5 Abhängigkeiten

| Abhängigkeit | Status | Voraussetzung für |
|--------------|--------|-------------------|
| **KEDA** | ⬜ Nicht installiert | Alle ScaledObjects |
| **RabbitMQ Prometheus Plugin** | ✅ Installiert | Queue-Metrics |
| **LiveKit Egress hostNetwork=false** | ⬜ Nicht umgesetzt | Parallele Recordings |
| **Prometheus Adapter** | ⬜ Nicht installiert | Custom Metrics |
| **Multi-Node Cluster** | ❌ Single-Node | LiveKit Autoscaling |

---

## 9. Bekannte Probleme & Lektionen

### 9.1 Cross-Namespace NetworkPolicy (KRITISCH — Production-Blocker)

**Problem:** KEDA läuft im Namespace `keda`, RabbitMQ im Namespace `meeting-automation`. Die NetworkPolicy `rabbitmq-allow-keda` erlaubt Ingress von `namespaceSelector: kubernetes.io/metadata.name: keda`, aber auf dem Production k3s-Cluster (Contabo, Calico) wird dieser Cross-Namespace-Traffic blockiert.

**Beweis:**
- Staging (OCI, ARM64): KEDA → RabbitMQ funktioniert ✅
- Production (Contabo, AMD64): KEDA → RabbitMQ `i/o timeout` ❌
- Test: `kubectl run test --rm -i --restart=Never --image=busybox -n keda -- nc -w3 10.42.0.192 5672` → TCP_FAIL

**Root Cause:** k3s Calico CNI auf Contabo hat andere Cross-Namespace-NetworkPolicy-Implementierung als OCI. Die `namespaceSelector` mit `kubernetes.io/metadata.name` wird nicht korrekt aufgelöst.

**Workaround (CI/CD):**
- In CI/CD muss nach KEDA-Install ein **Connectivity-Test** eingefügt werden:
  ```bash
  kubectl run keda-nettest --rm -i --restart=Never --image=busybox -n keda \
    -- sh -c "nc -w5 rabbitmq.meeting-automation.svc.cluster.local 5672 && echo OK || echo FAIL"
  ```
- Bei FAIL: NetworkPolicy `rabbitmq-allow-keda` muss manuell angepasst werden (z.B. `podSelector` statt `namespaceSelector`)

**Lösung (Produktion):**
1. Option A: KEDA in den gleichen Namespace wie App deployen (empfohlen)
2. Option B: NetworkPolicy mit `podSelector` statt `namespaceSelector` anpassen
3. Option C: Calico GlobalNetworkPolicy für Cross-Namespace-Traffic

### 9.2 RabbitMQ Readiness Probe

**Problem:** Production RabbitMQ war 0/1 Ready (Readiness-Probe `rabbitmq-diagnostics check_running` schlug fehl), obwohl RabbitMQ lief und Connections akzeptierte.

**Impact:** Service-Endpoints leer → KEDA ClusterIP-Verbindung `i/o timeout`

**Fix:** RabbitMQ StatefulSet neu starten (`kubectl rollout restart statefulset/rabbitmq -n meeting-automation`)

### 9.3 KEDA TriggerAuthentication vs. Inline-URL

**Problem:** KEDA RabbitMQ-Trigger mit `host: amqp://user:pass@...` in der YAML gab `invalid credentials` Error, obwohl das Passwort korrekt war.

**Root Cause:** URL-Parsing in KEDA v2.20.2 für URL-Sonderzeichen (`/` am Ende, URL-Encoding).

**Lösung:** `TriggerAuthentication` mit Secret-Referenz nutzen:
```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: rabbitmq-auth
spec:
  secretTargetRef:
    - parameter: host
      name: keda-rabbitmq-url
      key: host
```

---

## 10. Offene Punkte (aktualisiert 2026-08-14)

| Punkt | Priorität | Status |
|-------|-----------|--------|
| KEDA auf Staging installieren | P1 | ✅ Erledigt |
| KEDA ScaledObjects deployen | P1 | ✅ Erledigt (Staging) |
| Hardcoded HPA entfernen | P1 | ✅ Erledigt (Staging) |
| CI/CD Pipeline anpassen | P1 | ✅ Erledigt |
| Scale-to-Zero testen | P1 | ✅ Erledigt (Staging) |
| Production: Cross-Namespace-Fix | P1 | ❌ Blockiert (NetworkPolicy) |
| Production: Hardcoded HPA entfernen | P1 | ⏳ Wartet auf NetworkPolicy-Fix |
| LiveKit Egress hostNetwork entfernen | P2 | ⏳ Wartet auf Multi-Node |
| Rollback-Verfahren testen | P2 | ⬜ Offen |
| Prometheus Adapter installieren | P2 | ⬜ Offen |
| Multi-Node Cluster für Production | P3 | ⬜ Offen |

---

## 10. Test-Plan

### 10.1 Staging Test (nach KEDA-Install)

```
1. KEDA installieren
2. ScaledObjects deployen
3. 3 parallele Tenants testen
4. Prüfen: Skalieren die Workers dynamisch?
5. Prüfen: Funktioniert Scale-to-Zero?
6. Prüfen: Parallele Recordings (nach hostNetwork-Entfernung)
```

### 10.2 Erfolgskriterien

| Kriterium | Ergebnis |
|-----------|----------|
| KEDA installiert | Pods running in keda-ns |
| ScaledObjects aktiv | Status: Active |
| Scale-to-Zero | Workers = 0 bei leerer Queue |
| Scale-up | Workers = N bei N Messages |
| Parallele Recordings | 2+ Egress Pods bei Last |
| Rollback funktioniert | Hardcoded HPA wiederherstellbar |
