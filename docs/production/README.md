# Production Plan — Meeting Automation (Kubernetes)

> Erstellt: 2026-05-27 | Basis: Kubernetes MCP Live-Check + Docker-Compose Vergleich
> **Alle Lösungen: Open Source / Kostenlos**

## Übersicht

5 Sprints zur Produktionshärtung des Kubernetes-Clusters:

| Sprint | Scope | Dauer |
|--------|-------|-------|
| [Sprint 1](sprint-01-resource-limits-probes.md) | Resource Limits + Health Probes | Sofort |
| [Sprint 2](sprint-02-tls-registry.md) | cert-manager TLS + Image Registry | ~1 Woche |
| [Sprint 3](sprint-03-storage-backups.md) | Longhorn Storage + CloudNativePG + Velero Backups | ~2 Wochen |
| [Sprint 4](sprint-04-monitoring-hpa.md) | Prometheus/Grafana/Loki + HPA + PDB + AntiAffinity | ~3 Wochen |
| [Sprint 5](sprint-05-gitops-secrets.md) | ArgoCD GitOps + Environments + Secret Management | ~4 Wochen |

## Architektur

Siehe [Architektur-Diagramm](architecture.md).

## Aktuelle Lücken

### Critical (Sprint 1)

| # | Issue | Betroffen |
|---|---|---|
| 1 | Resource Limits fehlen | 9/11 Workloads |
| 2 | Health Probes fehlen | 7/11 Workloads |
| 3 | Kein TLS | Traefik Ingress |

### High (Sprint 2–3)

| # | Issue | Lösung |
|---|---|---|
| 4 | Storage hostpath | Longhorn (CNCF) |
| 5 | Image Registry | Docker Hub / Harbor (CNCF) |
| 6 | Keine Backups | Velero + MinIO (bereits im Cluster) |
| 7 | Kein Monitoring | kube-prometheus-stack (CNCF) |

### Medium (Sprint 4–5)

| # | Issue | Lösung |
|---|---|---|
| 8 | Kein HPA | Kubernetes HPA (built-in) |
| 9 | Kein PodAntiAffinity | Kubernetes built-in |
| 10 | Kein PDB | Kubernetes built-in |
| 11 | Nur ein Environment | Kubernetes Namespaces |
| 12 | Kein GitOps | ArgoCD (CNCF) |

## Lizenz-Übersicht

| Komponente | Lizenz | Typ |
|---|---|---|
| **Traefik** | MIT | Ingress Controller |
| **cert-manager** | Apache 2.0 | TLS-Zertifikate |
| **Longhorn** | Apache 2.0 (CNCF) | Block Storage |
| **Rook/Ceph** | Apache 2.0 (CNCF) | Storage (Alternativ) |
| **Harbor** | Apache 2.0 (CNCF) | Container Registry |
| **Docker Registry** | Apache 2.0 | Container Registry (minimal) |
| **Velero** | Apache 2.0 (CNCF) | Backup/Restore |
| **MinIO** | AGPL v3 | S3-kompatibler Storage |
| **Prometheus** | Apache 2.0 (CNCF) | Monitoring |
| **Grafana** | AGPL v3 | Dashboards |
| **Loki** | AGPL v3 (CNCF) | Log-Aggregation |
| **ArgoCD** | Apache 2.0 (CNCF) | GitOps |
| **CloudNativePG** | Apache 2.0 (CNCF) | PostgreSQL Operator |
| **Kustomize** | Apache 2.0 | Config Management |
| **SOPS** | MPL 2.0 | Secret Encryption |
| **Sealed Secrets** | Apache 2.0 | Secret Management |
