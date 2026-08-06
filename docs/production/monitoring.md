# Monitoring Bericht — Meeting Automation

**Date:** 2026-08-06
**Letzte Aktualisierung:** Phase 191 (Production Monitoring Stack)
**Server:** OCI Staging + Contabo Production

## Überblick

| Komponente | Staging | Production |
|------------|---------|------------|
| Prometheus | ✅ hostNetwork | ✅ hostNetwork |
| Grafana | ✅ | ✅ |
| Alertmanager | ✅ | ✅ |
| Node Exporter | ✅ | ✅ |
| kube-state-metrics | ✅ | ✅ |
| Targets UP | 15/15 | 18/18 |

## Zugriff

| Service | URL | Login |
|---------|-----|-------|
| Grafana | https://grafana.meeting-automation.com | admin / admin |
| Prometheus | https://monitoring.meeting-automation.com | admin / admin |
| Alertmanager | https://alertmanager.meeting-automation.com | admin / admin |

---

## Custom Dashboards (Meeting-optimiert)

### 1. Meeting Pipeline Overview
**UID:** `meeting-pipeline-overview`
**Quelle:** `grafana-dashboard-pipeline.yaml`

| Panel | Metrik | Was prüfen |
|-------|--------|------------|
| Meetings Created | `meeting_created_total` | Gesamtzahl Meetings pro Tag |
| Transcriptions Completed | `transcription_completed_total` | Erfolgreiche Transkriptionen |
| PVs Generated | `pv_generated_total` | Erfolgreiche PV-Generierung |
| Actions Extracted | `actions_extracted_total` | Extrahierte Aktionspunkte |
| Pipeline Duration | `pipeline_duration_seconds` | Gesamtzeit Recording → PV |
| Recording Duration | `recording_duration_seconds` | Dauer der Aufnahme |
| Transcription Duration | `transcription_duration_seconds` | Dauer der Transkription |
| PV Generation Duration | `pv_generation_duration_seconds` | Dauer der PV-Generierung |

**Wann prüfen:**
- Nach jedem Meeting: Sind Transkription und PV erstellt?
- Bei Verzögerungen: Welcher Schritt dauert zu lang?
- Bei Fehlern: Wo im Pipeline bricht etwas ab?

### 2. Meeting Pipeline Intelligence
**UID:** `meeting-pipeline-intelligence`
**Quelle:** `grafana-dashboard-intelligence.yaml`

| Panel | Metrik | Was prüfen |
|-------|--------|------------|
| Gladia Transcription Duration | `gladia_transcription_duration_seconds` | Dauer der Gladia-Transkription |
| Mistral PV Duration | `mistral_pv_generation_duration_seconds` | Dauer der Mistral-PV-Generierung |
| Speaker Identification Accuracy | `speaker_identification_accuracy` | Genauigkeit der Speaker-Erkennung |
| Assignee Resolution Confidence | `assignee_resolution_confidence` | Zuverlässigkeit der Aufgaben-Zuordnung |
| Phonetic Match Score | `phonetic_match_score` | Arabische Name-Matching-Qualität |
| Retry Count | `pipeline_retry_total` | Anzahl der Wiederholungen |
| Error Rate | `pipeline_error_total` | Fehler pro Pipeline-Schritt |

**Wann prüfen:**
- Bei schlechter PV-Qualität: Ist die Speaker-ID korrekt?
- Bei falschen Zuordnungen: Ist die Konfidenz niedrig?
- Bei Verzögerungen: Ist Gladia oder Mistral der Flaschenhals?

### 3. Tenant Analytics
**UID:** `meeting-tenant-analytics`
**Quelle:** `grafana-dashboard-tenants.yaml`

| Panel | Metrik | Was prüfen |
|-------|--------|------------|
| Meetings per Tenant | `tenant_meetings_total` | Anzahl Meetings pro Kunde |
| Storage Usage | `tenant_storage_bytes` | Speicherverbrauch pro Kunde |
| API Calls | `tenant_api_calls_total` | API-Aufrufe pro Kunde |
| Active Users | `tenant_active_users` | Aktive Benutzer pro Kunde |
| Transcription Minutes | `tenant_transcription_minutes_total` | Transkriptions-Minuten pro Kunde |
| PV Count | `tenant_pv_total` | PVs pro Kunde |
| Action Count | `tenant_actions_total` | Aktionspunkte pro Kunde |

**Wann prüfen:**
- Bei Kapazitätsplanung: Welcher Kunde verbraucht wie viel?
- Bei Preisgestaltung: Usage-basierte Abrechnung
- Bei Performance-Problemen: Ist ein Kunde "noisy neighbor"?

---

## Standard Dashboards (kube-prometheus-stack)

### Kubernetes Cluster

| Dashboard | Was prüfen |
|-----------|------------|
| **Kubernetes / API Server** | API-Server Latenz, Fehler, Request-Volume |
| **Kubernetes / Cluster Total** | Gesamt-Cluster-Auslastung (CPU, Memory) |
| **Kubernetes / CoreDNS** | DNS-Auflösung, Cache-Hit-Rate, Fehler |
| **Kubernetes / Controller Manager** | Controller-Reconciliation, Fehler |
| **Kubernetes / ETCD** | ETCD Latenz, Speicher, Snapshots |
| **Kubernetes / Kubelet** | Kubelet Status, Pod-Starts, Container-Restarts |
| **Kubernetes / Proxy** | kube-proxy Performance,iptables-rules |
| **Kubernetes / Scheduler** | Scheduling-Latenz, Failed-Schedules |

### Kubernetes Workloads

| Dashboard | Was prüfen |
|-----------|------------|
| **Kubernetes / Namespace (Pods)** | Pods pro Namespace, Status, Restarts |
| **Kubernetes / Node (Pods)** | Pods pro Node, Ressourcen-Verbrauch |
| **Kubernetes / Pod** | Einzelner Pod: CPU, Memory, Network, Restarts |
| **Kubernetes / Workload** | Deployment/StatefulSet/DaemonSet Status |
| **Kubernetes / Persistent Volumes** | PVC-Nutzung, Verfügbare Kapazität |

### Node & Infrastruktur

| Dashboard | Was prüfen |
|-----------|------------|
| **Node Exporter / Full** | Node CPU, Memory, Disk, Network |
| **Node Exporter / Filesystem** | Festplatten-Auslastung, I/O |
| **Node Exporter / Network** | Network-Traffic, Fehler, Paketverlust |
| **Node Exporter / Disk** | Disk I/O, Latenz, Auslastung |

### Prometheus & Monitoring

| Dashboard | Was prüfen |
|-----------|------------|
| **Prometheus / Stats** | Prometheus Internals: Scraping, Rules, Storage |
| **Prometheus / Alerts** | Aktive Alerts, History |
| **Prometheus / Rules** | Recording/Alerting Rules Status |

### Spezial-Dashboards

| Dashboard | Was prüfen |
|-----------|------------|
| **Kubernetes / Grafana** | Grafana Internals: Dashboards, Datenquellen |
| **Kubernetes / Kube State Metrics** | Cluster-Objekte: Deployments, Services, ConfigMaps |
| **Kubernetes / Resources (Cluster)** | Gesamt-Cluster-Ressourcen |
| **Kubernetes / Resources (Namespace)** | Ressourcen pro Namespace |
| **Kubernetes / Resources (Pod)** | Ressourcen pro Pod |
| **Kubernetes / Workload (Namespace)** | Workloads pro Namespace |
| **Kubernetes / Persistent Volume Usage** | Speichernutzung pro PVC |

---

## ServiceMonitors

| Monitor | Target | Port | Pfad | Interval |
|---------|--------|------|------|----------|
| `meeting-automation-backend` | Backend Pods | 8000 | `/metrics` | 30s |
| `kube-prometheus-stack-apiserver` | API Server | 6443 | `/metrics` | 30s |
| `kube-prometheus-stack-coredns` | CoreDNS | 9153 | `/metrics` | 30s |
| `kube-prometheus-stack-grafana` | Grafana | 3000 | `/metrics` | 30s |
| `kube-prometheus-stack-kubelet` | Kubelet | 10250 | `/metrics` | 30s |
| `kube-prometheus-stack-kube-state-metrics` | Kube State Metrics | 8080 | `/metrics` | 30s |
| `kube-prometheus-stack-prometheus` | Prometheus | 9090 | `/metrics` | 30s |
| `kube-prometheus-stack-prometheus-node-exporter` | Node Exporter | 9100 | `/metrics` | 30s |

---

## Alerting Rules

### Kubernetes Alerts

| Alert | Bedingung | Severity |
|-------|-----------|----------|
| `KubePodCrashLooping` | Pod crashed > 5 times in 10min | critical |
| `KubePodNotReady` | Pod not ready > 15min | critical |
| `KubeDeploymentReplicasMismatch` | Desired ≠ Available > 15min | warning |
| `KubeNodeNotReady` | Node not ready > 15min | critical |
| `KubePersistentVolumeUsageCritical` | PVC > 85% | warning |
| `KubePersistentVolumeUsageCritical` | PVC > 95% | critical |

### Meeting-automation Alerts

| Alert | Bedingung | Severity |
|-------|-----------|----------|
| `MeetingPipelineHighLatency` | Pipeline > 180s | warning |
| `MeetingPipelineFailed` | Pipeline-Fehler > 0 | critical |
| `TranscriptionFailed` | Transkription fehlgeschlagen | critical |
| `PVGenerationFailed` | PV-Generierung fehlgeschlagen | critical |
| `SpeakerIdentificationLowConfidence` | Confidence < 0.5 | warning |
| `BackendHighErrorRate` | 5xx Fehler > 5% | critical |
| `BackendHighLatency` | P95 Latenz > 2s | warning |

---

## Recording Rules

| Rule | Metrik | Zweck |
|------|--------|-------|
| `meeting:pipeline_duration_seconds:avg` | Durchschnittliche Pipeline-Dauer | Trend-Analyse |
| `meeting:transcription_duration_seconds:avg` | Durchschnittliche Transkriptions-Dauer | Gladia-Performance |
| `meeting:pv_generation_duration_seconds:avg` | Durchschnittliche PV-Dauer | Mistral-Performance |
| `meeting:api_requests_total:rate5m` | API Request Rate | Last-Monitoring |
| `meeting:api_errors_total:rate5m` | API Error Rate | Fehler-Monitoring |

---

## Quick-Reference: Was prüfen bei Problemen?

### Meeting nicht sichtbar
1. `Meeting Pipeline Overview` → Meetings Created = 0?
2. `meeting-automation-backend` ServiceMonitor → Backend erreichbar?
3. Prometheus Targets → Alle UP?

### PV nicht generiert
1. `Meeting Pipeline Intelligence` → Transcription Duration = 0?
2. `meeting-automation-recording-rules` → Gladia-Fehler?
3. Celery Worker Logs → Task fehlgeschlagen?

### Langsame Performance
1. `Kubernetes / API Server` → API-Latenz hoch?
2. `Kubernetes / Pod` → Backend-Pod CPU/Memory?
3. `Node Exporter / Full` → Node überlastet?

### Speicher voll
1. `Kubernetes / Persistent Volume Usage` → PVC > 85%?
2. `Tenant Analytics` → Storage Usage pro Kunde?
3. MinIO → S3-Speicher voll?

### Fehler in der Pipeline
1. `Meeting Pipeline Intelligence` → Error Rate hoch?
2. `meeting-automation-alerts` → Aktive Alerts?
3. Prometheus Targets → DOWN targets?

---

## CI/CD Integration

Die Monitoring-Stacks werden automatisch deployed:

| Step | Staging | Production |
|------|---------|------------|
| Namespace erstellen | ✅ | ✅ |
| Helm install/upgrade | ✅ | ✅ |
| Monitoring-Configs | ✅ | ✅ |
| Rollout-Status prüfen | ✅ | ✅ |

**Korrekte Reihenfolge:** Helm → CRDs → Configs
