## Priorisierte Roadmap für Produktion (Security & ISO 27001)

Basierend auf dem jüngsten Security-Audit (ISO 27001:2022) wurden folgende Architektur-Erweiterungen und Maßnahmen als kritisch eingestuft und umgesetzt:

- [x] **Sofort (Phase 1)**: Secret Management. Migration aller Credentials (DB, API-Keys) aus der lokalen .env-Datei in einen sicheren Speicher (SOPS mit age-Verschlüsselung für Kubernetes Secrets).
- [x] **Kurzfristig**: Netzwerksegmentierung. Isolierung von Datenbank, Redis und Message Broker in strikt getrennten Kubernetes Namespaces mittels NetworkPolicies.
- [x] **Kurzfristig**: Infrastruktur & Startup-Stabilisierung (Probes, Ressourcen, RabbitMQ Fixes).
- [x] **Parallel**: API Gateway & Rate Limiting. Einsatz von Traefik vor Nginx zur Abwehr von DDoS, Bot-Management und Zero-Trust Access.
- [x] **Vor Go-Live**:
    - Session Management: Implementierung von Session-Fixation Protection und automatischer Terminierung bei Inaktivität.
    - JWT-Härtung: Reduzierung der `ACCESS_TOKEN_EXPIRE_MINUTES` von 1440 (24h) auf 30 Minuten.
    - [x] SSL/TLS: Verschlüsselung für jeglichen Traffic (auch intern via HTTPS/TLS).

## Roadmap für Phase 2 (Feature Expansion)

Nach dem erfolgreichen Abschluss der ISO 27001 Security Roadmap fokussiert sich die nächste Entwicklungsphase auf fehlende Funktionen und Endpunkte laut Projektzielen (Objectifs).

- [x] **1. Action Suggestions (ML-basiert)**:
  - `GET /api/v1/actions/suggestions/{meeting_id}`: Vorschläge für wiederkehrende Aktionen.
  - `POST /api/v1/actions/suggestions/learn`: Endpoint für ML-Lernzyklen.
- [x] **2. Speaker Attribution (Diarization)** via Gladia V2.
- [x] **3. PV Versioning** (ISO 27001 konform).
- [x] **4. Custom Branding für Exporte**.
- [x] **5. Action History / Patterns (Analytics Dashboard)**.
- [x] **6. Multilingual Export** (AR, FR, EN) inkl. RTL-Support und On-the-fly Inhaltsübersetzung.


## Historie & Protokolle

Die detaillierte Entwicklungshistorie und technische Dokumentation der Meilensteine ist in den folgenden konsolidierten Protokollen zu finden:

1. **[Kubernetes Stabilität & Ressourcen](PROTOCOL_PART_35_KUBERNETES_STABILITY_AND_RESOURCES.md)**: Härtung der K8s-Infrastruktur, Optimierung des Ressourcenverbrauchs und Implementierung von Health-Checks.
2. **[SSL/TLS Encryption](PROTOCOL_PART_33_SSL_TLS_ENCRYPTION.md)**: Konfiguration von Traefik für erzwungenes HTTPS mit selbstsignierten Zertifikaten.
3. **[Session Management & JWT](PROTOCOL_PART_32_SESSION_MANAGEMENT.md)**: Implementierung von Auto-Logout und Token-Härtung (30 Minuten).
4. **[Traefik Rate Limiting](PROTOCOL_PART_31_TRAEFIK_RATE_LIMITING.md)**: Einführung von Traefik als API Gateway mit Rate Limiting (DDoS Schutz).
5. **[Network Segmentation](PROTOCOL_PART_30_NETWORK_SEGMENTATION.md)**: Implementierung von Kubernetes NetworkPolicies für Zero-Trust Sicherheit.
6. **[Kubernetes Setup Script & Key Security](PROTOCOL_PART_29_KUBERNETES_SETUP_SCRIPT.md)**: Erstellung eines automatisierten Setup-Skripts für K8s inkl. SOPS Key Management.
7. **[Kubernetes Setup Fixes](PROTOCOL_PART_28_KUBERNETES_SETUP_FIXES.md)**: Vollständige K8s-Migration des docker-compose Setups inkl. Nginx/CORS Fixes.
8. **[Secret Management Phase 1](PROTOCOL_PART_27_SECRET_MANAGEMENT_PHASE_1.md)**: Migration von Secrets zu SOPS-verschlüsselten Kubernetes Secrets mit age.
9. **[AI Phase 2 Finalisierung](PROTOCOL_PART_34_AI_PHASE_2_FINALIZATION.md)**: Integration von Gladia V2 und Analytics Dashboard.
10. **[Frontend i18n Fix](PROTOCOL_PART_26_FRONTEND_I18N_FIX.md)**: Behebung von Lokalisierungsproblemen im Frontend.
11. **[Core Pipeline: Audio & KI](PROTOCOL_CORE_PIPELINE_AI_&_AUDIO.md)**: Umfassende Dokumentation der Recording-Architektur, S3-Streaming, Whisper/Mistral-Integration und PDF-Export.
12. **[Diarization Fix](PROTOCOL_DIARIZATION_FIX.md)**: Historisches Protokoll zur Behebung von Problemen bei der Sprechererkennung (mittlerweile durch Gladia V2 ersetzt).
13. **[Infrastruktur & Startup-Stabilisierung](PROTOCOL_INFRASTRUCTURE_&_STARTUP_STABILIZATION.md)**: Details zu Docker-Caching, Schema-Migrationen und Container-Abhängigkeiten.
14. **[Umfassender System-Audit 2026](PROTOCOL_COMPREHENSIVE_SYSTEM_AUDIT_2026.md)**: Dokumentation des 100% Audits (Phasen 1-5), der Netzwerk-Fixes und der Test-Validierung.
15. **[Security UI & QA](PROTOCOL_SECURITY_UI_&_QA.md)**: ISO 27001 Compliance, sicherer Logout, Audit-Logging und rollenbasierte Dashboards.
16. **[n8n Automation & SMTP](PROTOCOL_N8N_AUTOMATION_&_SMTP.md)**: Konfiguration der Workflow-Engine, SMTP-Migration und Webhook-Härtung.
