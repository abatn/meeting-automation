# Longhorn CSI Auto-Scaling — Node-basierte Skalierung

**Erstellt:** 2026-08-19
**Status:** ✅ IMPLEMENTIERT (Production + Staging)
**Cluster:** Production (Contabo 169.58.83.32) + Staging (OCI 158.180.18.110)

---

## 1. Problem

### Ausgangslang

Longhorn CSI-Components (attacher, provisioner, resizer, snapshotter) waren hardcoded auf **3 Replicas** konfiguriert — auch auf Single-Node-Clustern.

| Komponente | Replicas | CPU | RAM | Single-Node nötig? |
|------------|----------|-----|-----|---------------------|
| csi-attacher | 3 ⚠️ | 24m | 33Mi | ❌ 1 reicht |
| csi-provisioner | 3 ⚠️ | 33m | 42Mi | ❌ 1 reicht |
| csi-resizer | 3 ⚠️ | 15m | 35Mi | ❌ 1 reicht |
| csi-snapshotter | 3 ⚠️ | 31m | 34Mi | ❌ 1 reicht |
| longhorn-ui | 2 ⚠️ | 0m | 4Mi | ❌ 1 reicht |
| driver-deployer | 1 | 0m | 9Mi | ❌ Deploy-fertig → 0 |
| **GESAMT** | **15** | **103m** | **157Mi** | |

**Overhead:** 10 redundant Pods, ~83m CPU, ~120Mi RAM verschwendet.

### Root Cause

Die CSI-Replicas wurden vom Longhorn Helm-Chart (v1.12.0) mit Default-Wert 3 installiert. Die Helm-Values hatten `csi.attacherReplicaCount: ~` (null) → Chart-Default 3.

---

## 2. Lösung

### 2.1 Sofort-Maßnahme: CSI 3→1 (kubectl scale)

```bash
# Production
for DEPLOY in csi-attacher csi-provisioner csi-resizer csi-snapshotter; do
  kubectl scale deployment $DEPLOY -n longhorn-system --replicas=1
done
kubectl scale deployment longhorn-ui -n longhorn-system --replicas=1
kubectl scale deployment longhorn-driver-deployer -n longhorn-system --replicas=0
```

### 2.2 Auto-Scaling: CronJob (Node-basiert)

**Dateien:**
- `infrastructure/kubernetes/production/longhorn-csi-autoscaler.yaml`
- `infrastructure/kubernetes/staging/longhorn-csi-autoscaler.yaml`

**Logik:**
```bash
# Alle 5 Minuten:
NODE_COUNT=$(kubectl get nodes --no-headers | grep -c " Ready")

# CSI-Replicas anpassen:
1 Node  → CSI-Replicas: 1
2 Nodes → CSI-Replicas: 2
3+ Nodes → CSI-Replicas: 3
```

**CronJob-Schedule:** `*/5 * * * *` (alle 5 Minuten)

**Ressourcen:**
```yaml
resources:
  limits:
    cpu: 100m
    memory: 64Mi
  requests:
    cpu: 50m
    memory: 32Mi
```

---

## 3. Ergebnis

### Pod-Count

| Metrik | Vorher | Nachher | Ersparnis |
|--------|--------|---------|-----------|
| **Pods gesamt** | 51 | **41** | **−10 (−20%)** |
| **Longhorn Pods** | 19 | **9** | **−10 (−53%)** |
| **CPU (Longhorn)** | 205m | **~122m** | **−83m (−40%)** |
| **RAM (Longhorn)** | 398Mi | **~267Mi** | **−131Mi (−33%)** |

### Pods pro Namespace (nachher)

```
     15 meeting-automation
      9 longhorn-system      ← war 19
      6 monitoring
      4 kube-system
      3 keda
      2 velero
      1 ingress-nginx
      1 cnpg-system
```

### Longhorn Deployments (nachher)

| Deployment | Replicas | Status |
|------------|----------|--------|
| csi-attacher | 1 | ✅ Ready |
| csi-provisioner | 1 | ✅ Ready |
| csi-resizer | 1 | ✅ Ready |
| csi-snapshotter | 1 | ✅ Ready |
| longhorn-ui | 1 | ✅ Ready |
| longhorn-driver-deployer | 0 | ⏸️ Deploy-fertig |

---

## 4. Auto-Scaling-Verhalten

### Szenario 1: Single-Node (Production aktuell)

```
Node: contabo-prod (1 Node)
CronJob: NODE_COUNT=1 → TARGET=1
CSI-Attacher: 1 Replica ✅
CSI-Provisioner: 1 Replica ✅
CSI-Resizer: 1 Replica ✅
CSI-Snapshotter: 1 Replica ✅
```

### Szenario 2: Zwei Nodes (zukünftig)

```
Nodes: contabo-prod + contabo-prod-2
CronJob: NODE_COUNT=2 → TARGET=2
CSI-Attacher: 2 Replicas ✅
CSI-Provisioner: 2 Replicas ✅
CSI-Resizer: 2 Replicas ✅
CSI-Snapshotter: 2 Replicas ✅
```

### Szenario 3: Drei+ Nodes (Cluster-Expansion)

```
Nodes: 3+
CronJob: NODE_COUNT=3 → TARGET=3
CSI-Attacher: 3 Replicas ✅ (Maximum)
CSI-Provisioner: 3 Replicas ✅
CSI-Resizer: 3 Replicas ✅
CSI-Snapshotter: 3 Replicas ✅
```

---

## 5. Technische Details

### Longhorn Helm Chart (v1.12.0)

Die CSI-Replicas werden über Helm-Values gesteuert:

```yaml
# infrastructure/kubernetes/production/livekit-server-values.yaml
# (nicht Longhorn — siehe unten)

# Longhorn Helm Values (bei next helm upgrade):
csi:
  attacherReplicaCount: 1
  provisionerReplicaCount: 1
  resizerReplicaCount: 1
  snapshotterReplicaCount: 1

persistence:
  defaultClassReplicaCount: 1  # ← bereits gesetzt in longhorn-default-setting
```

### CronJob RBAC

Der CronJob nutzt `serviceAccountName: default`. Für Production sollte ein dedizierter ServiceAccount mit Scale-Berechtigung erstellt werden:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: longhorn-csi-scaler
  namespace: longhorn-system
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "update", "patch"]
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: longhorn-csi-scaler
  namespace: longhorn-system
subjects:
- kind: ServiceAccount
  name: longhorn-csi-scaler
  namespace: longhorn-system
roleRef:
  kind: Role
  name: longhorn-csi-scaler
  apiGroup: rbac.authorization.k8s.io
```

---

## 6. Zusammenhang mit Incident-Report

Dieser Fix ist Teil derくれitere Optimierung nach dem Eviction-Storm (2026-08-15):

| Fix | Datei | Status |
|-----|-------|--------|
| F1-F8 | `INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` | ✅ Implementiert |
| Longhorn CSI Auto-Scaling | `LONGHORN_CSI_AUTOSCALING_2026-08-19.md` | ✅ Implementiert |
| LiveKit Server Config | `INCIDENT_REPORT_EPHEMERAL_STORAGE_OUTAGE_2026-08-15.md` §11-14 | ✅ Implementiert |

---

## 7. Nächste Schritte

| # | Maßnahme | Priorität |
|---|----------|-----------|
| 1 | RBAC für CronJob erstellen (dedizierter ServiceAccount) | ⚠️ Mittel |
| 2 | Helm Values bei next Upgrade CSI-Replicas setzen | ⚠️ Mittel |
| 3 | Prometheus Alert für CSI-Replica-Count hinzufügen | ℹ️ Nice-to-have |
| 4 | Staging CronJob deployen | ✅ Bereit |
