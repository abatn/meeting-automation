# Rollback-Plan: Production auf 05.08.2026 (Commit 8f2116ee)

## Ziel
Production-Cluster auf den Stand vom 5. August 2026 bringen — **OHNE Velero, Longhorn, Prometheus, Grafana**.

## Status: 8f2116ee
- **Datum:** 2026-08-05 02:23:18 UTC
- **Beschreibung:** `fix(n8n): /n8n subpath fix — Staging deployed, Production ready`
- **Pipeline:** 80/80 Meetings COMPLETED am 05.08 auf Staging

---

## Kategorisierung der Änderungen seit 8f2116ee

### 🔴 REVERTEN (Infrastruktur-Additionen die Probleme verursacht haben)

| Datei | Änderung | Grund |
|-------|----------|-------|
| `monitoring/*.yaml` (5 Dateien) | Prometheus/Grafana hinzugefügt | Verursacht 122K Watch-Events, 2% CPU |
| `velero-schedule.yaml` | Velero Schedule hinzugefügt | CI/CD blockiert wenn Velero aus |
| `velero-values.yaml` | Velero Helm Values | CI/CD Risiko |
| `prometheus-values.yaml` | Prometheus Helm Values | CI/CD Risiko |
| `metrics-server.yaml` | Metrics Server hinzugefügt | CI/CD Risiko |
| `keda-scaledobjects.yaml` | KEDA ScaledObjects | CI/CD Risiko |
| `keda-rabbitmq-networkpolicy.yaml` | KEDA NetworkPolicy | CI/CD Risiko |
| `k3s-config.yaml` | k3s Config | CI/CD Risiko |

### 🟡 BEHALTEN (Korrekte Fixes die behalten werden müssen)

| Datei | Änderung | Grund |
|-------|----------|-------|
| `backend-config.yaml` | +SENTINEL_MODEL_URL | Sentinel LLM funktioniert |
| `celery-worker-pro-deployment.yaml` | mountPath=/app/models | Sentinel Fix vom 14.08 |
| `cnpg-cluster.yaml` | replicationSlots, retentionPolicy=7d | HA + Speicher-Optimierung |
| `frontend-nginx-config.yaml` | OnlyOffice Routing-Fix | OnlyOffice funktioniert |
| `onlyoffice-*.yaml` | OnlyOffice Fixes | OnlyOffice funktioniert |
| `livekit-configmap.yaml` | LiveKit Config | LiveKit funktioniert |

### ⚠️ PRÜFEN (Können behalten oder revertet werden)

| Datei | Änderung | Empfehlung |
|-------|----------|------------|
| `cnpg-scheduled-backup.yaml` | ScheduledBackup | Behalten (DB-Sicherheit) |
| `postgres-backup-cronjob.yaml` | Backup CronJob | Behalten (DB-Sicherheit) |
| `network-policies.yaml` | NetworkPolicies | Behalten (Sicherheit) |

---

## Revert-Schritte

### Phase 1: Monitoring CRDs + Helm Charts entfernen

```bash
# 1.1 Monitoring CRDs löschen (bereits gemacht - 10 CRDs)
kubectl delete crd alertmanagerconfigs.monitoring.coreos.com --ignore-not-found
kubectl delete crd alertmanagers.monitoring.coreos.com --ignore-not-found
# ... (bereits erledigt)

# 1.2 Monitoring Namespace löschen (wenn vorhanden)
kubectl delete namespace monitoring --ignore-not-found

# 1.3 Prometheus Helm Release entfernen
helm uninstall kube-prometheus-stack -n monitoring --ignore-not-found
```

### Phase 2: Velero deaktivieren

```bash
# 2.1 Velero Deploy auf 0/0 (bereits gemacht)
kubectl scale deployment velero -n velero --replicas=0

# 2.2 Velero Node-Agent auf 0/0 (bereits gemacht)
kubectl patch ds node-agent -n velero --type=json -p='[{"op": "replace", "path": "/spec/template/spec/nodeSelector", "value": {"non-existing": "true"}}]'

# 2.3 Velero Schedule löschen
kubectl delete schedule daily-backup -n velero --ignore-not-found
```

### Phase 3: KEDA ScaledObjects entfernen

```bash
# 3.1 KEDA ScaledObjects löschen
kubectl delete scaledobject keda-hpa-backend -n meeting-automation --ignore-not-found
kubectl delete scaledobject keda-hpa-celery-worker-pro -n meeting-automation --ignore-not-found
kubectl delete scaledobject keda-hpa-livekit-egress -n meeting-automation --ignore-not-found
```

### Phase 4: Metrics Server entfernen

```bash
# 4.1 Metrics Server Deployment löschen
kubectl delete deployment metrics-server -n kube-system --ignore-not-found
kubectl delete service metrics-server -n kube-system --ignore-not-found
```

### Phase 5: k3s Config bereinigen

```bash
# 5.1 k3s Config prüfen und bereinigen
# GOGC=50 und GOMEMLIMIT=1500MiB behalten (hilfreich)
# kubelet-arg behalten (hilfreich)
```

### Phase 6: CNPG Backup behalten

```bash
# 6.1 CNPG ScheduledBackup behalten (DB-Sicherheit)
# 6.2 Replication Slots behalten (HA)
# 6.3 retentionPolicy=7d behalten (Speicher)
```

---

## Verifikation nach Revert

| Test | Erwartung |
|------|-----------|
| **Staging Pipeline** | 80/80 Meetings COMPLETED |
| **Production Pods** | Alle Running, keine Fehler |
| **Production CPU** | <50% (statt 65%) |
| **CRDs** | <30 (statt 44) |
| **Watch-Events** | <3.5M (statt 3.9M) |

---

## Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung |
|--------|-------------------|------------|
| **Datenverlust** | Niedrig | Nur Infrastruktur-Änderungen |
| **Pipeline funktioniert nicht** | Niedrig | Code ist identisch |
| **Velero Backups weg** | Mittel | CNPG Backups bleiben |
| **Monitoring weg** | Hoch | Kein Prometheus/Grafana |

---

## Empfehlung

**Nur Phase 1 (Monitoring) und Phase 3 (KEDA) durchführen** — das sind die Hauptverursacher der CPU-Last. Velero und Metrics Server können behalten werden wenn sie kein Problem verursachen.
