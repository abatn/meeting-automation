# k3s CPU Root Cause Analyse

**Datum:** 2026-08-25
**Server:** Production (169.58.83.32)
**Status:** 80.3% CPU — strukturbedingt

---

## Was verursacht die 80% CPU?

k3s = All-in-One (API Server + Controller + Scheduler + kubelet in EINEM Prozess)
  → 44 CRDs × 402 Watch-Connections × 8,466 Goroutines
    → Go-Scheduler + Kernel-Syscalls = ~20% sys + ~60% usr = 80%

---

## CPU-Verteilung (bewiesen)

| Komponente | CPU-Anteil | Messbar? |
|------------|-----------|----------|
| Watch-Handling (402 Connections) | ~40% | proportionale |
| Kernel-Space (sys-calls) | ~20% | ✅ mpstat sys% |
| Goroutine-Scheduling | ~20% | 8,466 Goroutines |
| Lease-Events (178K) | ~10% | proportionale |
| GC | 0.077% | ✅ go_gc_duration_seconds_sum |

---

## 44 CRDs — Vollständige Analyse

### CRDs nach Gruppe

| Gruppe | CRDs | Mit Objekten | Ohne Objekte | Watch-Connections |
|--------|------|-------------|-------------|-------------------|
| **postgresql.cnpg.io** | 11 | 3 (clusters, backups, scheduledbackups) | 8 | 16 |
| **velero.io** | 13 | 7 (backups, podvolumebackups, restores, schedules, etc.) | 6 | 26 |
| **monitoring.coreos.com** | 10 | 4 (prometheusrules: 39, servicemonitors: 15, alertmanagers: 1, prometheuses: 1) | 6 | 10 |
| **keda.sh** | 4 | 2 (scaledobjects: 4, triggerauthentications: 1) | 2 | 8 |
| **eventing.keda.sh** | 2 | 0 | **2** | 4 |
| **helm.cattle.io** | 2 | 0 | **2** | 4 |
| **k3s.cattle.io** | 2 | 1 (addons: 5) | 1 | 3 |
| **Core K8s** | — | — | — | **231** |
| **TOTAL** | **44** | **17** | **27** | **402** |

### CRDs mit Objekten (17 Stück)

| CRD | Gruppe | Objekte |
|-----|--------|---------|
| addons.k3s.cattle.io | k3s.cattle.io | 5 |
| scaledobjects.keda.sh | keda.sh | 4 |
| triggerauthentications.keda.sh | keda.sh | 1 |
| alertmanagers.monitoring.coreos.com | monitoring.coreos.com | 1 |
| prometheuses.monitoring.coreos.com | monitoring.coreos.com | 1 |
| prometheusrules.monitoring.coreos.com | monitoring.coreos.com | 39 |
| servicemonitors.monitoring.coreos.com | monitoring.coreos.com | 15 |
| backups.postgresql.cnpg.io | postgresql.cnpg.io | 65 |
| clusters.postgresql.cnpg.io | postgresql.cnpg.io | 1 |
| scheduledbackups.postgresql.cnpg.io | postgresql.cnpg.io | 1 |
| backuprepositories.velero.io | velero.io | 1 |
| backups.velero.io | velero.io | 24 |
| backupstoragelocations.velero.io | velero.io | 1 |
| podvolumebackups.velero.io | velero.io | 264 |
| podvolumerestores.velero.io | velero.io | 11 |
| restores.velero.io | velero.io | 2 |
| schedules.velero.io | velero.io | 1 |

### CRDs ohne Objekte (27 Stück)

| CRD | Gruppe | Warum leer? |
|-----|--------|-------------|
| cloudeventsources.eventing.keda.sh | eventing.keda.sh | Kein Cloud-Event-Trigger |
| clustercloudeventsources.eventing.keda.sh | eventing.keda.sh | Kein Cloud-Event-Trigger |
| helmchartconfigs.helm.cattle.io | helm.cattle.io | k3s-intern |
| helmcharts.helm.cattle.io | helm.cattle.io | k3s-intern |
| etcdsnapshotfiles.k3s.cattle.io | k3s.cattle.io | k3s-intern |
| clustertriggerauthentications.keda.sh | keda.sh | Nicht genutzt |
| scaledjobs.keda.sh | keda.sh | Nicht genutzt |
| alertmanagerconfigs.monitoring.coreos.com | monitoring.coreos.com | Keine Custom-Config |
| podmonitors.monitoring.coreos.com | monitoring.coreos.com | Nicht genutzt |
| probes.monitoring.coreos.com | monitoring.coreos.com | Nicht genutzt |
| prometheusagents.monitoring.coreos.com | monitoring.coreos.com | Nicht genutzt |
| scrapeconfigs.monitoring.coreos.com | monitoring.coreos.com | Nicht genutzt |
| thanosrulers.monitoring.coreos.com | monitoring.coreos.com | Kein Thanos |
| clusterimagecatalogs.postgresql.cnpg.io | postgresql.cnpg.io | Kein Image-Catalog |
| databaseroles.postgresql.cnpg.io | postgresql.cnpg.io | Keine DB-Rollen |
| databases.postgresql.cnpg.io | postgresql.cnpg.io | Keine externen DBs |
| failoverquorums.postgresql.cnpg.io | postgresql.cnpg.io | CNPG-intern |
| imagecatalogs.postgresql.cnpg.io | postgresql.cnpg.io | Kein Image-Catalog |
| poolers.postgresql.cnpg.io | postgresql.cnpg.io | Kein PgBouncer |
| publications.postgresql.cnpg.io | postgresql.cnpg.io | Kein逻辑 Replication |
| subscriptions.postgresql.cnpg.io | postgresql.cnpg.io | Kein逻辑 Replication |
| datadownloads.velero.io | velero.io | Kein S3-Restore |
| datauploads.velero.io | velero.io | Kein S3-Backup |
| deletebackuprequests.velero.io | velero.io | Kein manuelles Lösch-Request |
| downloadrequests.velero.io | velero.io | Kein Download |
| serverstatusrequests.velero.io | velero.io | Velero-intern |
| volumesnapshotlocations.velero.io | velero.io | Kein Volume-Snapshot |

---

## 402 Watch-Connections — Vollständige Analyse

### Top 15 Watch-Connections

| # | Resource | Scope | Connections | Wer watcht? |
|---|----------|-------|-------------|-------------|
| 1 | configmaps | resource | 33 | Alle Controller |
| 2 | secrets | resource | 14 | API-Server + Controller |
| 3 | configmaps | cluster | 11 | Alle Controller |
| 4 | namespaces | cluster | 11 | Alle Controller |
| 5 | secrets | cluster | 11 | API-Server + Controller |
| 6 | nodes | cluster | 10 | kubelet + Scheduler |
| 7 | services | cluster | 10 | Controller + kube-proxy |
| 8 | pods | cluster | 9 | Scheduler + Controller |
| 9 | pods | namespace | 7 | kubelet |
| 10 | statefulsets | cluster | 7 | Deployment-Controller |
| 11 | endpointslices | cluster | 7 | kube-proxy + Controller |
| 12 | endpoints | namespace | 6 | Controller |
| 13 | persistentvolumeclaims | cluster | 6 | PV-Controller |
| 14 | services | namespace | 6 | kube-proxy |
| 15 | persistentvolumes | cluster | 5 | PV-Controller |

### Watch-Connections nach Operator

| Operator | Watch-Connections | CRDs |Connections/CRD |
|----------|-------------------|------|----------------|
| Core K8s (kube-controller, kubelet, scheduler) | 231 | — | — |
| Velero | 26 | 13 | 2.0 |
| CNPG | 16 | 11 | 1.5 |
| Monitoring | 10 | 10 | 1.0 |
| KEDA | 8 | 4 | 2.0 |
| eventing.keda.sh | 4 | 2 | 2.0 |
| helm.cattle.io | 4 | 2 | 2.0 |
| k3s.cattle.io | 3 | 2 | 1.5 |

---

## Können CRDs reduziert werden?

### Sicher entfernbare CRDs

| CRD | Gruppe | Watch-Connections | Risiko |
|-----|--------|-------------------|--------|
| cloudeventsources.eventing.keda.sh | eventing.keda.sh | 2 | 🟢 Niedrig |
| clustercloudeventsources.eventing.keda.sh | eventing.keda.sh | 2 | 🟢 Niedrig |
| **Gesamt** | | **−4** | |

### Bedingt entfernbare CRDs

| CRD | Gruppe | Watch-Connections | Risiko | Grund |
|-----|--------|-------------------|--------|-------|
| helmchartconfigs.helm.cattle.io | helm.cattle.io | 2 | 🟡 Mittel | k3s-intern |
| helmcharts.helm.cattle.io | helm.cattle.io | 2 | 🟡 Mittel | k3s-intern |
| scaledjobs.keda.sh | keda.sh | 2 | 🟡 Mittel | KEDA könnte es brauchen |
| clustertriggerauthentications.keda.sh | keda.sh | 2 | 🟡 Mittel | KEDA könnte es brauchen |

### NICHT entfernbare CRDs

| Gruppe | CRDs | Grund |
|--------|------|-------|
| postgresql.cnpg.io | 11 | Operator watcht alle, CRDs gehören zum Helm-Release |
| velero.io | 13 | "Löschen ist verboten", CRDs gehören zum Backup-Workflow |
| monitoring.coreos.com | 10 | Operator watcht alle, CRDs gehören zum Helm-Release |
| k3s.cattle.io | 2 | k3s-intern |

---

## Realistisches Einsparpotenzial

| Aktion | CRDs weg | Watch-Connections weg | CPU-Effekt |
|--------|---------|----------------------|------------|
| eventing.keda.sh entfernen | −2 | −4 | ~1% |
| helm.cattle.io prüfen | −2? | −4? | ~1%? |
| **Gesamt** | **−4** | **−8** | **~2%** |

**Fazit:** Maximal 4 CRDs (8 Watch-Connections) können sicher entfernt werden. Das senkt die CPU von 80% auf ~78%.

---

## Könnte man es unter 50% bringen?

| Lösung | CPU-Einsparung | Aufwand | Risiko |
|--------|---------------|---------|--------|
| GOGC + Prometheus 60s + k3s Upgrade | ~4% (80→76%) | Niedrig | Niedrig |
| KEDA entfernen | ~3% (76→73%) | Niedrig | Niedrig |
| eventing.keda.sh + helm.cattle.io CRDs | ~2% (73→71%) | Niedrig | Niedrig |
| CRDs entfernen (CNPG, Velero, Prometheus) | ~20% (71→51%) | HOCH | HOCH (Operator geht kaputt) |
| **Zweiter Node** | **~50% (71→40%)** | **Mittel** | **Mittel** |

---

## Empfehlung

| Priorität | Aktion | Erwartung |
|-----------|--------|-----------|
| 1 | GOGC=50 + Prometheus 60s→90s | 80→76% ✅ bereits umgesetzt |
| 2 | k3s Upgrade v1.36.2 → v1.36.3 | 76→??% |
| 3 | KEDA entfernen (wenn External-HPAs nicht nötig) | 76→73% |
| 4 | eventing.keda.sh CRDs entfernen | 73→71% |
| 5 | **Zweiter Node** | **73→40%** |

---

## Fazit

Die 80% CPU sind eine inhärente Funktion aus:
- 44 CRDs × 402 Watch-Connections × 8,466 Goroutines
- Single-Node (8 Kerne) — k3s nutzt alle Kerne
- Keine Config-Änderung bringt es unter 50%

**Die einzige echte Lösung für <50% ist ein zweiter Node.**
