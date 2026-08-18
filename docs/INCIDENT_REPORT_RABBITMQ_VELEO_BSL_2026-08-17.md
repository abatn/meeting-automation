# Incident Report: RabbitMQ Readiness + Velero BSL Unavailable

**Erstellt:** 2026-08-17 14:30 UTC
**Cluster:** Production (Contabo, 169.58.83.32)
**Schweregrad:** P2 (Velero-Backups fehlgeschlagen, aber App funktioniert)
**Status:** ✅ Resolved (2026-08-18)

---

## 1. Zusammenfassung

Der RabbitMQ-Pod auf Production hat eine Readiness-Probe mit `timeoutSeconds: 3` —
obwohl die StatefulSet-Spec bereits `timeoutSeconds: 10` gesetzt hat. Der Pod wurde
nach dem `kubectl apply` NICHT neu gestartet. `rabbitmq-diagnostics check_running`
braucht auf Production unter Last ~5-8s → 3s-Timeout reicht nicht → Pod bleibt
`Ready: False` → MinIO nicht erreichbar → Velero BSL `Unavailable` → Daily-Backup
`FailedValidation`.

---

## 2. Timeline

| Zeit (UTC) | Event | Details |
|------------|-------|---------|
| 2026-08-16 18:12 | rabbitmq-0 Pod erstellt | `kubectl apply` im Deploy-Script |
| 2026-08-16 18:12 | Pod bekommt alten Probe | `timeoutSeconds: 3` (vor dem Fix) |
| 2026-08-16 ~18:20 | Readiness-Fehler beginnen | `rabbitmq-diagnostics check_running timed out after 3s` |
| 2026-08-16 20:04 | Deploy Production abgeschlossen | `ab8ae5f` — StatefulSet Spec auf `timeoutSeconds: 10` aktualisiert |
| 2026-08-16 20:04 | **Pod NICHT neu gestartet** | `kubectl apply` aktualisiert Spec, aber kein Rollout-Restart |
| 2026-08-17 02:00 | Daily-Backup getriggert | Schedule `daily-backup` um 02:00 UTC |
| 2026-08-17 02:00 | Backup FailedValidation | Velero BSL Unavailable → `connection refused` auf MinIO:9000 |
| 2026-08-17 02:00–14:30 | Readiness-Fehler akkumulieren | 5,558+ Fehlversuche in 15h |
| 2026-08-17 14:30 | Incident erkannt | Pod zeigt `timeoutSeconds: 3`, Spec zeigt `10` |

---

## 3. Root Cause

### Die Diskrepanz

| Komponente | timeoutSeconds | Quelle |
|-----------|----------------|--------|
| **StatefulSet Spec** | **10** ✅ | `kubectl apply` aus `rabbitmq-statefulset.yaml` |
| **Laufender Pod** | **3** 🔴 | Alter Pod, nie neu gestartet |

### Warum?

`kubectl apply` bei StatefulSets aktualisiert die Spec, aber:
1. **Kein automatic Rollout** — StatefulSets rollout-en nur bei Spec-Änderungen die
   einen neuen Pod-Template erzeugen (Image, Command, etc.)
2. **Probe-Änderungen allein** lösen keinen Rollout aus
3. **Resultat:** Der laufende Pod behält den alten Probe

### Beweis

```
StatefulSet Generation:        5 (applied)
StatefulSet observedGeneration: 5 (synced)
Pod Creation:                   2026-08-16T18:12:18Z (VOR dem Deploy-Fix)
Pod Probe:                      timeoutSeconds: 3 (ALT)
Spec Probe:                     timeoutSeconds: 10 (NEU)
```

---

## 4. Impact

### Direkt betroffen

| Komponente | Status | Impact |
|-----------|--------|--------|
| RabbitMQ | 🔴 Ready: False | Service erreichbar, aber nicht im Endpoints |
| Velero BSL | 🔴 Unavailable | Kein Backup möglich |
| Daily-Backup | ❌ FailedValidation | Kein Backup seit 02:00 UTC |
| celery-worker-pro | ⚠️ 147 Restarts | Liveness-Problem wegen RabbitMQ |
| CPU Load | ⚠️ 13.6 (170%) | rabbitmq-diagnostics verbrennt CPU |

### NICHT betroffen

| Komponente | Status |
|-----------|--------|
| Backend (2/2) | ✅ Running |
| Frontend | ✅ Running |
| Meeting-DB (3/3) | ✅ Running |
| MinIO | ✅ Running |
| n8n | ✅ Running |
| LiveKit | ✅ Running |
| App-Funktionalität | ✅ Alle API-Endpunkte erreichbar |

---

## 5. Sofortige Korrektur

### 5.1 Pod neu starten (Benötigt SSH)

```bash
ssh root@169.58.83.32
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
sudo /usr/local/bin/k3s kubectl rollout restart statefulset/rabbitmq -n meeting-automation
sudo /usr/local/bin/k3s kubectl rollout status statefulset/rabbitmq -n meeting-automation --timeout=120s
```

**Dauer:** ~30 Sekunden
**Risiko:** RabbitMQ ist kurzzeitig nicht erreichbar (StatefulSet-Rolling-Update)
**Erwartung:** Neuer Pod bekommt `timeoutSeconds: 10` → `rabbitmq-diagnostics`
schafft es → Ready: True → MinIO erreichbar → Velero BSL Available

### 5.2 Verifikation nach Restart

```bash
# Pod Ready?
kubectl get pod -n meeting-automation rabbitmq-0 -o jsonpath="{.status.conditions[?(@.type=='Ready')].status}"
# Erwartung: True

# Neuer Probe?
kubectl get pod -n meeting-automation rabbitmq-0 -o jsonpath="{.spec.containers[0].readinessProbe.timeoutSeconds}"
# Erwartung: 10

# Velero BSL?
velero backup-location get
# Erwartung: Available

# CPU Load?
uptime
# Erwartung: < 10 (rabbitmq-diagnostics CPU-Verbrauch weg)
```

---

## 6. Permanente Fixes

### F1: deploy-all.sh um Rollout-Restart erweitern

**Problem:** `kubectl apply` bei StatefulSets löst keinen Rollout aus für Probe-Änderungen.

**Lösung:** Nach jedem `kubectl apply` für StatefulSets einen expliziten Rollout-Restart:
```bash
# In scripts/deploy-prod/02-apply-manifests.sh
kubectl apply -f rabbitmq-statefulset.yaml
kubectl rollout restart statefulset/rabbitmq -n $NAMESPACE
kubectl rollout status statefulset/rabbitmq -n $NAMESPACE --timeout=120s
```

**Status:** ⬜ Offen — muss in `deploy-all.sh` + `deploy-staging.sh` implementiert werden

### F2: CI/CD Pre-Deploy-Check

**Problem:** Kein Check ob StatefulSet-Pods den neuen Spec haben.

**Lösung:** Nach `kubectl apply` prüfen ob Pod-Spec mit Spec übereinstimmt:
```bash
POD_TIMEOUT=$(kubectl get pod rabbitmq-0 -o jsonpath='{.spec.containers[0].readinessProbe.timeoutSeconds}')
SPEC_TIMEOUT=$(kubectl get statefulset rabbitmq -o jsonpath='{.spec.template.spec.containers[0].readinessProbe.timeoutSeconds}')
if [ "$POD_TIMEOUT" != "$SPEC_TIMEOUT" ]; then
  echo "⚠️ RabbitMQ Pod probe mismatch — rollout restart needed"
  kubectl rollout restart statefulset/rabbitmq
fi
```

**Status:** ⬜ Offen — muss in Deploy-Scripts implementiert werden

---

## 7. Kette der Abhängigkeiten

```
kubectl apply (rabbitmq-statefulset.yaml)
  → StatefulSet Spec: timeoutSeconds = 10 ✅
  → Pod NICHT neu gestartet (kein Rollout ausgelöst)
  → Pod behält: timeoutSeconds = 3 🔴
  → rabbitmq-diagnostics check_running: 5-8s unter Last
  → Readiness-Probe: timeout nach 3s → FAILED
  → rabbitmq-0: Ready: False
  → rabbitmq.meeting-automation.svc:5672 → keine Endpoints
  → MinIO → rabbitmq nicht erreichbar
  → Velero BSL: "connection refused" → Unavailable
  → daily-backup-20260817020054: FailedValidation
  → Kein Backup seit 02:00 UTC
  → CPU: rabbitmq-diagnostics = 69.6% (Teufelskreis)
```

---

## 8. Lektionen

| # | Lektion | Umsetzung |
|---|---------|-----------|
| 1 | `kubectl apply` bei StatefulSets löst KEINEN Rollout für Probe-Änderungen aus | Immer `kubectl rollout restart` nach apply für StatefulSets |
| 2 | StatefulSet-Pods laufen endlos ohne Neustart | Immer Pod-Spec gegen Spec-Spec prüfen nach Deploy |
| 3 | RabbitMQ `rabbitmq-diagnostics` braucht auf Production >3s unter Last | timeoutSeconds: 10 ist Minimum für Production |
| 4 | Velero BSL hängt von MinIO ab → MinIO hängt von RabbitMQ ab | Velero-Backup-Status muss nach Deploy geprüft werden |
| 5 | Deploy-Script muss StatefulSet-Rollouts verwalten | deploy-all.sh braucht Rollout-Restart für StatefulSets |

---

## 9. Offene Punkte

| # | Punkt | Priorität | Verantwortlich |
|---|-------|-----------|---------------|
| 1 | RabbitMQ Pod auf Production neu starten | 🔴 P1 | SSH zu Contabo |
| 2 | deploy-all.sh um Rollout-Restart erweitern | 🟡 P2 | CI/CD Agent |
| 3 | deploy-staging.sh um Rollout-Restart erweitern | 🟡 P2 | CI/CD Agent |
| 4 | CI/CD Pre-Deploy-Check für StatefulSet-Sync | 🟢 P3 | CI/CD Agent |
| 5 | celery-worker-pro 147 Restarts dokumentieren | 🟢 P3 | Monitoring |

---

## 10. Vergleich Staging vs Production

| Parameter | Staging | Production |
|-----------|---------|------------|
| RabbitMQ Ready | ✅ **True** | 🔴 **False** |
| Pod Probe | `timeoutSeconds: 10` ✅ | `timeoutSeconds: 3` 🔴 |
| Pod Alter | Frisch (nach Rollout) | 18h alt (kein Rollout) |
| Velero BSL | ✅ Available | 🔴 Unavailable |
| Letztes Backup | ✅ Completed | ❌ FailedValidation |
| CPU Load | 59% (normal) | 170% (rabbitmq-diagnostics) |

**Staging funktioniert** weil der RabbitMQ-Pod nach dem Fix neu gestartet wurde
(Rolling Update durch Deploy). Auf Production wurde der Pod nie neu gestartet.

---

## 11. Resolution (2026-08-18)

### Root Cause (korrigiert)

Die ursprüngliche Analyse聚焦te auf RabbitMQ (timeoutSeconds: 3). Die **tatsächliche
Ursache** war ein NetworkPolicy-Problem: Die `minio-policy` in beiden Clustern hatte
**keinen `namespaceSelector` für Velero**. Velero läuft im `velero` Namespace, aber
die Policy erlaubte nur Pods aus dem `meeting-automation` Namespace.

### Änderungen

| Datei | Zeile | Änderung |
|-------|-------|----------|
| `infrastructure/kubernetes/production/network-policies.yaml` | 165 | Velero NamespaceSelector zu minio-policy hinzugefügt |
| `infrastructure/kubernetes/staging/network-policies.yaml` | 164 | Velero NamespaceSelector zu minio-policy hinzugefügt |
| `infrastructure/kubernetes/production/minio-statefulset.yaml` | 15 | Self-Reference Annotation hinzugefügt |
| `infrastructure/kubernetes/staging/minio-statefulset.yaml` | 15 | Self-Reference Annotation hinzugefügt |

### Verifizierung

```bash
$ grep -A 3 "kubernetes.io/metadata.name: velero" infrastructure/kubernetes/*/network-policies.yaml
production/network-policies.yaml:165:          kubernetes.io/metadata.name: velero   # Velero BSL → MinIO Zugriff
staging/network-policies.yaml:164:          kubernetes.io/metadata.name: velero   # Velero BSL → MinIO Zugriff

$ grep "backup.velero.io/backup-volumes-excludes" infrastructure/kubernetes/*/minio-statefulset.yaml
production/minio-statefulset.yaml:15:        backup.velero.io/backup-volumes-excludes: "minio-data"  # Self-Reference verhindern
staging/minio-statefulset.yaml:15:        backup.velero.io/backup-volumes-excludes: "minio-data"  # Self-Reference verhindern
```

### Deploy-Status

| Cluster | Mechanismus | Status |
|---------|-------------|--------|
| **Staging** | Auto-Deploy via `workflow_run` | ✅ Deployed bei Push auf main |
| **Production** | Manuell via `workflow_dispatch` | ⚠️ Benötigt manuellen Trigger |
