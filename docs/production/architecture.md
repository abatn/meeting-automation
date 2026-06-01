# Architektur (Open Source Stack)

```
┌───────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                         │
├───────────────────────────────────────────────────────────────┤
│  Namespace: meeting-automation                                 │
│                                                                │
│  ┌────────────┐  ┌────────────────┐  ┌──────────────────────┐ │
│  │  Traefik   │  │  cert-manager  │  │  Monitoring           │ │
│  │  Ingress   │  │ (Let's Encrypt)│  │  Prometheus+Grafana   │ │
│  └─────┬──────┘  └────────────────┘  │  +Loki (CNCF)          │ │
│        │                              └──────────────────────┘ │
│  ┌─────▼──────────────────────────────────────────────────┐   │
│  │              Ingress (TLS via Let's Encrypt)            │   │
│  ├──────────┬──────────┬────────┬──────────┬──────────────┤   │
│  │ backend  │ frontend │  n8n   │onlyoffice│   celery     │   │
│  │  (HPA)   │  (HPA)   │        │          │    w+b       │   │
│  ├──────────┴──────────┴────────┴──────────┴──────────────┤   │
│  │                Services (ClusterIP)                     │   │
│  ├──────────┬──────────┬────────┬──────────┬──────────────┤   │
│  │ postgres │  redis   │rabbitmq│  minio   │   Longhorn   │   │
│  │  (CNPG)  │          │        │(S3+Backup)│  (Storage)   │   │
│  └──────────┴──────────┴────────┴──────────┴──────────────┘   │
│                                                                │
│  GitOps: ArgoCD (CNCF)   │   Secrets: SOPS (Mozilla)          │
│  Registry: Harbor (CNCF) │   Backups: Velero + MinIO          │
└───────────────────────────────────────────────────────────────┘
```

## Komponenten

### Ingress & Netzwerk
- **Traefik** — Ingress Controller (HTTP/HTTPS Routing, Middleware)
- **cert-manager** — Automatische Let's Encrypt TLS-Zertifikate

### Anwendungen (Workloads)
| Komponente | Beschreibung | HPA | PDB |
|---|---|---|---|
| **backend** | FastAPI + asyncpg | ja | ja |
| **frontend** | React + Vite (nginx) | ja | ja |
| **n8n** | Workflow Automation | nein | nein |
| **onlyoffice** | Dokumenteneditor | nein | nein |
| **celery-worker** | Async Tasks | nein | nein |
| **celery-beat** | Scheduled Tasks | nein | nein |

### Datenhaltung
| Komponente | Typ | HA | Backup |
|---|---|---|---|
| **PostgreSQL** (CloudNativePG) | Relationale DB | Replikation | Velero + pg_dump |
| **Redis** | Cache + Celery Broker | Sentinel | — |
| **RabbitMQ** | Message Queue | Quorum Queues | — |
| **MinIO** | S3-kompatibler Storage | Erasure Coding | Velero |

### Infrastruktur
| Komponente | Zweck |
|---|---|
| **Longhorn** | Block Storage (PVCs) mit Snapshots & Replikation |
| **Harbor** | Private Container Registry mit Vulnerability Scanning |
| **Velero** | Cluster-Backups + Restore |
| **Prometheus + Grafana** | Metriken & Dashboards |
| **Loki** | Log-Aggregation |
| **ArgoCD** | GitOps Deployment |
| **SOPS / Sealed Secrets** | Secret Encryption |
