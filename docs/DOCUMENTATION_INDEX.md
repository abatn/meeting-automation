# Dokumentation Übersicht — Meeting Automation System

> Automatisch kategorisiert: 2026-06-24 | 115+ Dateien in `docs/`
> **Status**: k3s Staging aktiv, 21 Pods Running, Pipeline 31.7s, Phase 53 abgeschlossen (cert-manager + nginx-ingress)

## 1. Architektur & Systemdesign

| Datei | Beschreibung |
|-------|-------------|
| `ARCHITECTURE.md` | **Hauptdokument** — System-Architektur, Pipeline-Flow, Deployment-Map, Security |
| `ARCHITECTURE_DIAGRAM.md` | Mermaid-Diagramm des Datenflusses |
| `DATABASE_SCHEMA.md` | DB-Schema (9 Tabellen, validiert 2026-05-10) |
| `CONTEXT_FOR_AI.md` | KI-Session-Kontext (Projektstatus, Architektur, nächste Schritte) |
| `CULTURAL_ADAPTATIONS.md` | Tunesien/Maghreb-Anpassungen (Arabisch, RTL, WhatsApp) |
| `SAAS_MULTI_TENANT_BRIEFING.md` | Multi-Tenancy-Architektur (RBAC, client_id) |
| `IMPLEMENTATION_PROTOCOLS.md` | Übersicht aller Implementierungs-Protokolle |

## 2. LiveKit Recording Pipeline

| Datei | Beschreibung |
|-------|-------------|
| `LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` | **Hauptdokument** — Kompletter Recording-Pipeline-Flow |
| `LIVEKIT_INTEGRATION_PLAN.md` | LiveKit-Integrationsplan (Echtzeit-Audio + Recording) |
| `LIVEKIT_PRODUCTION_ARCHITECTURE.md` | Host-basiertes Deployment (UDP-Gründe, Kind-Limitierungen) |
| `LIVEKIT_PRODUCTION_HARDENING_ROADMAP.md` | Production Hardening (Monitoring, Backup, TLS) |
| `LIVEKIT_E2E_TESTING.md` | E2E-Test-Strategie für LiveKit |
| `LIVEKIT_EGRESS_ICE_FIX_2026-06-06.md` | ICE-Verbindungsfix (Egress → LiveKit) |
| `LIVEKIT_CONNECTION_FIX_2026-06-09.md` | Connection-Fix (Signal-URLs, WebRTC) |
| `LIVEKIT_CONNECTION_INSTABILITY_ANALYSIS_2026-06-11.md` | Instabilitätsanalyse (WebRTC, ICE) |
| `LIVEKIT_URL_FIX_2026-06-11.md` | URL-Fix (PUBLIC_URL, Webhook) |
| `LIVEKIT_TIER2_VERIFICATION_2026-06-06.md` | Tier-2 Pipeline Hardening Verification |

## 3. KI-Pipeline (Transcription, PV, Actions)

| Datei | Beschreibung |
|-------|-------------|
| `DUAL_CONTEXT_PV_GENERATION.md` | **Dual-Context PV** — Display Transcript + Sentinel |
| `INTELLIGENT_SPEAKER_ASSIGNMENT.md` | 5-Schritt Assignee Resolution |
| `01-speaker-assignment-problem.md` | Speaker Assignment Problem-Analyse |
| `02-speaker-assignment-solution.md` | Microsoft Teams Architektur Lösung |
| `03-implementation-plan.md` | Implementation Plan Speaker Assignment |
| `PHASE_7_SUGGESTION_PIPELINE_CRITICAL_RULES.md` | Critical Rules für Vorschlags-Pipeline |
| `PIPELINE_OPTIMIZATION_2026-06-12.md` | Pipeline-Optimierung (Gladia V2, Timing) |
| `PIPELINE_QUICK_WINS.md` | Quick Wins (1-2h, bestehender Stack) |
| `PIPELINE_STATUS_2026-04-06.md` | Pipeline-Status (historisch) |
| `PROTOCOL_CORE_PIPELINE_AI_&_AUDIO.md` | Protokoll: Audio + KI-Verarbeitung |
| `PROTOCOL_DIARIZATION_FIX.md` | Protokoll: Diarization-Fix (historisch) |
| `PROTOCOL_PHASE_4_AI_PIPELINE.md` | Protokoll: KI-Pipeline Phase 4 |

## 4. Speaker Identification & Diarization

| Datei | Beschreibung |
|-------|-------------|
| `PHASE8_SPEAKER_IDENTIFICATION_RESULTS.md` | ONNX-Speaker-ID Ergebnisse |
| `SPEAKER_RESOLUTION_FIX_2026-06-05.md` | Speaker Resolution Fix |
| `FIX_SPEAKER_NAMES_IN_PV.md` | Speaker Names in PV korrigiert |
| `PROTOCOL_PHASE_8_SPEAKER_IDENTIFICATION.md` | Protokoll: Speaker Identification |
| `PROTOCOL_DIARIZATION_FIX.md` | Protokoll: Diarization (historisch) |

## 5. Kubernetes & Staging (k3s)

| Datei | Beschreibung |
|-------|-------------|
| `production/` | **Produktions-Roadmap** (5 Sprints) |
| `production/architecture.md` | Referenz-Architektur (Zielzustand) |
| `production/k3s-migration-analysis.md` | Kind → k3s Analyse + Migration |
| `production/sprint-01-resource-limits-probes.md` | Sprint 1: Resources + Probes |
| `production/sprint-02-tls-registry.md` | Sprint 2: TLS + Registry |
| `production/sprint-03-storage-backups.md` | Sprint 3: Storage + HA + Backups |
| `production/sprint-04-monitoring-hpa.md` | Sprint 4: Monitoring + HPA |
| `production/sprint-5-gitops-secrets.md` | Sprint 5: GitOps + Secrets |
| `STAGING_DB_SCHEMA_DRIFT_2026-06-22.md` | DB Schema Drift (Alembic) |
| `STAGING_ENUM_DRIFT_2026-06-22.md` | Enum Drift (meetingstatus) |
| `STAGING_PIPELINE_TEST_RESULTS_2026-06-22.md` | Pipeline Test-Ergebnisse |
| `STAGING_RECOVERY_PLAN.md` | Recovery & Rekonstruktionsplan (k3s) |
| `STAGING_CLUSTER_SETUP_PLAN.md` | Cluster Setup (k3s) |
| `ROADMAP_STAGING_VS_PRODUCTION.md` | Staging vs Production Gap Analysis |
| `kubernetes-deployment-workarounds.md` | **HISTORISCH** — Kind-Workarounds (Phase 1-32) |
| `PRODUCTION_DEPLOYMENT_PLAN.md` | Production Deployment Plan |
| `PRODUCTION_PLAN.md` | Production Plan (Kubernetes) |

## 6. Security & Compliance

| Datei | Beschreibung |
|-------|-------------|
| `ISO27001.md` | **ISO 27001 Compliance** — Controls, Roadmap, Status (13 NetworkPolicies) |
| `PHASE1_SECURITY_FIXES.md` | Kritische Security Fixes (JWT, bcrypt, Fernet) |
| `FALSE_ALARMS_AUDIT_2026-06-05.md` | False Alarms Security Audit |
| `PROTOCOL_PART_27_SECRET_MANAGEMENT_PHASE_1.md` | Secret Management Phase 1 |
| `PROTOCOL_PART_30_NETWORK_SEGMENTATION.md` | Network Segmentation |
| `PROTOCOL_PART_31_TRAEFIK_RATE_LIMITING.md` | Rate Limiting |
| `PROTOCOL_PART_32_SESSION_MANAGEMENT.md` | Session Management |
| `PROTOCOL_PART_33_SSL_TLS_ENCRYPTION.md` | SSL/TLS Verschlüsselung |
| `PROTOCOL_SECURITY_UI_&_QA.md` | Security UI & QA |

## 7. Frontend & UI

| Datei | Beschreibung |
|-------|-------------|
| `PROFESSIONAL_INTELLIGENT_UI_PLAN.md` | Professionelle Meeting UI |
| `PROTOCOL_PART_26_FRONTEND_I18N_FIX.md` | Frontend i18n Fix |
| `PROTOCOL_PART_42_DASHBOARD_UI_REDESIGN.md` | Dashboard UI Redesign |
| `PROTOCOL_PART_43_MOBILE_RTL_STABILIZATION.md` | Mobile + RTL Stabilisierung |
| `UI_CONSISTENCY_TECHNICAL_DEBT.md` | UI Technical Debt |
| `FIX_MEETING_STATUS_ENUM.md` | Meeting Status Enum Fix |
| `onlyoffice/Nginx-Redirect-Fix.md` | OnlyOffice Nginx Fix |

## 8. n8n Integration

| Datei | Beschreibung |
|-------|-------------|
| `LIVEKIT_N8N_WORKFLOWS.md` | n8n Workflow Activation Guide |
| `N8N_INTEGRATION_GUIDE.md` | n8n Integration Guide |
| `N8N_QUICKSTART_GUIDE.md` | n8n Quickstart |
| `N8N_WORKFLOWS.md` | n8n Workflow Integration |
| `PROTOCOL_N8N_AUTOMATION_&_SMTP.md` | Protokoll: n8n Automatisierung |
| `SMTP_CREDENTIAL_CLEANUP.md` | SMTP Credential Cleanup |

**Status (Phase 48):** n8n 7 Workflows importiert und aktiv via API. NodePort 31678 für Web UI.

## 9. Pipeline & Recording

| Datei | Beschreibung |
|-------|-------------|
| `LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` | **Haupt-Pipeline-Dokument** |
| `PIPELINE_OPTIMIZATION_2026-06-12.md` | Pipeline-Optimierung |
| `PIPELINE_QUICK_WINS.md` | Quick Wins |
| `PIPELINE_STATUS_2026-04-06.md` | Pipeline-Status |
| `pipeline-onlyoffice-pdf-edit.md` | OnlyOffice PDF Edit Pipeline |
| `pipeline-pv-validate-pdf.md` | PV Validate → PDF Email Pipeline |
| `plan-onlyoffice-pdf-in-n8n-pipeline.md` | OnlyOffice PDF in n8n Pipeline |

## 10. Protokolle (chronologisch)

| Datei | Datum | Thema |
|-------|-------|-------|
| `PROTOCOL_COMPREHENSIVE_SYSTEM_AUDIT_2026.md` | 27.02.2026 | System-Audit |
| `PROTOCOL_INFRASTRUCTURE_&_STARTUP_STABILIZATION.md` | 20-26.02.2026 | Infrastruktur |
| `PROTOCOL_DIARIZATION_FIX.md` | 23.02.2026 | Diarization |
| `PROTOCOL_CORE_PIPELINE_AI_&_AUDIO.md` | 15.03.2026 | Audio + KI |
| `PROTOCOL_PHASE_2_TEAM_MANAGEMENT.md` | — | Team Management |
| `PROTOCOL_PHASE_3_MEETING_LIFECYCLE.md` | — | Meeting Lifecycle |
| `PROTOCOL_PHASE_4_AI_PIPELINE.md` | — | KI Pipeline |
| `PROTOCOL_PHASE_5_ACTION_ASSIGNMENT.md` | — | Action Assignment |
| `PROTOCOL_PHASE_6_N8N_AUTOMATION.md` | — | n8n Automation |
| `PROTOCOL_PHASE_7_MINIO_INTEGRATION.md` | — | MinIO Integration |
| `PROTOCOL_PHASE_8_SPEAKER_IDENTIFICATION.md` | — | Speaker ID |
| `PROTOCOL_PART_26_FRONTEND_I18N_FIX.md` | 08.03.2026 | Frontend i18n |
| `PROTOCOL_PART_27_SECRET_MANAGEMENT_PHASE_1.md` | 09.03.2026 | Secrets |
| `PROTOCOL_PART_28_KUBERNETES_SETUP_FIXES.md` | 09.03.2026 | K8s Setup |
| `PROTOCOL_PART_29_KUBERNETES_SETUP_SCRIPT.md` | 09.03.2026 | K8s Script |
| `PROTOCOL_PART_30_NETWORK_SEGMENTATION.md` | 09.03.2026 | Network |
| `PROTOCOL_PART_31_TRAEFIK_RATE_LIMITING.md` | — | Rate Limiting |
| `PROTOCOL_PART_32_SESSION_MANAGEMENT.md` | — | Sessions |
| `PROTOCOL_PART_33_SSL_TLS_ENCRYPTION.md` | — | SSL/TLS |
| `PROTOCOL_PART_34_AI_PHASE_2_FINALIZATION.md` | — | AI Phase 2 |
| `PROTOCOL_PART_35_KUBERNETES_STABILITY_AND_RESOURCES.md` | — | K8s Stability |
| `PROTOCOL_PART_36_SAAS_MULTI_TENANT_TRANSFORMATION.md` | — | Multi-Tenant |
| `PROTOCOL_PART_37_BILLING_LANDING_MONITORING.md` | — | Billing + Monitoring |
| `PROTOCOL_PART_39_ADVANCED_MONITORING.md` | — | Monitoring |
| `PROTOCOL_PART_40_MEETING_PLANNER_EXTENSION.md` | — | Meeting Planner |
| `PROTOCOL_PART_41_ONLYOFFICE_INTEGRATION.md` | — | OnlyOffice |
| `PROTOCOL_PART_42_DASHBOARD_UI_REDESIGN.md` | — | Dashboard |
| `PROTOCOL_PART_43_MOBILE_RTL_STABILIZATION.md` | — | Mobile RTL |
| `PROTOCOL_PART_44_ENTERPRISE_ONBOARDING_WORKFLOW.md` | — | Enterprise Onboarding |
| `PROTOCOL_PART_45_ENTERPRISE_ONBOARDING_AUTO_LOGIN.md` | — | Auto Login |
| `PROTOCOL_PART_46_SESSION_2026_04_24_COMPLETION.md` | 24.04.2026 | Session Abschluss |
| `PROTOCOL_ISS_FINAL_VALIDATION.md` | 27.03.2026 | ISS Validation |
| `PROTOCOL_SECURITY_UI_&_QA.md` | — | Security UI QA |

## 11. Status & Berichte

| Datei | Beschreibung |
|-------|-------------|
| `PROJECT_STATUS.md` | Aktueller Projektstatus (2026-06-18) |
| `PROJECT_COMPLETION_SUMMARY.md` | Projekt-Abschluss |
| `IMPLEMENTATION_SUMMARY.md` | P1 Fixes Zusammenfassung |
| `FINAL_SYSTEM_CHECK.md` | Finaler System-Check |
| `MASTER_ANALYSIS_ALL_PHASES.md` | Umfassende End-to-End Analyse |
| `DEPLOYMENT_PIPELINE_STATUS_2026-04-05.md` | Deployment Pipeline Status |
| `E2E_VALIDATION_REPORT_2026-04-05.md` | E2E Staging Validation |
| `QUALITY_METRICS.md` | Qualitätmetriken |
| `PR_SUMMARY.md` | PR Zusammenfassung |

## 12. PDF & OnlyOffice

| Datei | Beschreibung |
|-------|-------------|
| `pdf-generation-methods-analysis.md` | PDF-Generierung Methoden |
| `implementation-plan-pdf-s3-fallback.md` | PDF Download mit S3-Prüfung |
| `pipeline-onlyoffice-pdf-edit.md` | OnlyOffice PDF Edit Pipeline |
| `pipeline-pv-validate-pdf.md` | PV Validate → PDF Email |
| `plan-onlyoffice-pdf-in-n8n-pipeline.md` | OnlyOffice PDF in n8n |
| `onlyoffice/Nginx-Redirect-Fix.md` | Nginx Redirect Fix |

## 13. Onboarding & Billing

| Datei | Beschreibung |
|-------|-------------|
| `PROTOCOL_PART_44_ENTERPRISE_ONBOARDING_WORKFLOW.md` | Enterprise Onboarding |
| `PROTOCOL_PART_45_ENTERPRISE_ONBOARDING_AUTO_LOGIN.md` | Auto Login |
| `PROTOCOL_PART_36_SAAS_MULTI_TENANT_TRANSFORMATION.md` | Multi-Tenant |
| `PROTOCOL_PART_37_BILLING_LANDING_MONITORING.md` | Billing + Monitoring |
| `STRIPE_SETUP.md` | Stripe Einrichtung |

## 14. Sonstiges

| Datei | Beschreibung |
|-------|-------------|
| `LINT_ISSUES_2026-04-05.md` | Technical Debt (Linting) |
| `PROTOCOL_PART_46_SESSION_2026_04_24_COMPLETION.md` | Session-Abschluss |

---

## Zusammenfassung

| Kategorie | Anzahl Dateien | Prioritaet |
|-----------|---------------|-----------|
| Architektur & Systemdesign | 7 | Hoch |
| LiveKit Pipeline | 10 | **Kritisch** |
| KI-Pipeline | 10 | **Kritisch** |
| Kubernetes & Staging (k3s) | 14 | Hoch |
| Security & Compliance | 9 | Hoch |
| Frontend & UI | 6 | Mittel |
| n8n Integration | 6 | Mittel |
| Protokolle | 30+ | Niedrig (historisch) |
| Status & Berichte | 8 | Mittel |
| PDF & OnlyOffice | 6 | Mittel |
| Onboarding & Billing | 4 | Mittel |

**Hauptdokumente (lesen zuerst):**
1. `ARCHITECTURE.md` — Gesamtarchitektur + Pipeline + k3s Deployment-Map
2. `GETTING_STARTED.md` — Einstieg (Pipeline, Stack, Multi-Tenancy, Compliance)
3. `production/README.md` — Produktions-Roadmap (5 Sprints)
4. `production/k3s-migration-analysis.md` — Kind → k3s Analyse + Vorteile
5. `ISO27001.md` — Security Compliance (13 NetworkPolicies, 6/10 Controls)
6. `DATABASE_SCHEMA.md` — DB-Schema (9 Tabellen)

**Aktueller Stand (Phase 50):**
- 13 Pods Running auf k3s v1.35.5+k3s1
- Pipeline: 31.7s (Target ≤90s)
- Migration Chain: 1 Head (`n2o3p4q5r6s7`)
- 13 NetworkPolicies (ISO 27001 A.8.20)
- n8n: 7 Workflows importiert und aktiv (Phase 48)
- 0 hardcoded IPs, 0 hardcoded Credentials
- TLS: HTTP-only (deferred to Sprint 5)
