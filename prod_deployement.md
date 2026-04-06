E2E-Testing Framework Integration: Analyse & Umsetzungsplan

  ---
  1. Bestandsaufnahme

  1.1 Vorhandene Test-Tools und Frameworks

  Das Projekt nutzt bereits einen vollständigen pytest-basierten Stack:

  - pytest 7.4.4 als Kern-Framework
  - pytest-asyncio 0.23.3 für asynchrone Tests (FastAPI/SQLAlchemy)
  - pytest-rerunfailures 13.0 für automatische Wiederholung flaky Tests (--reruns 2)
  - pytest-cov 4.1.0 für Coverage-Messung
  - httpx 0.26.0 als asynchroner HTTP-Client für API-Calls
  - faker 22.0.0 für Testdaten-Generierung
  - locust (ohne fixe Version) für Last-Tests
  - aiosqlite 0.19.0 für SQLite in Unit-Tests
  - Kein Playwright, kein Behave, kein Selenium - rein API-basierte E2E-Tests

  1.2 Wo liegen die E2E-Test-Skripte

  Die relevanten Pfade sind:

  - backend/tests/e2e/ ist das primäre E2E-Verzeichnis mit 7 Testdateien: test_smoke.py, test_meeting_creation_flow.py,
  test_recording_transcription_pipeline.py, test_pv_generation_flow.py, test_action_status_e2e.py, test_n8n_webhook_integration.py
  und conftest.py
  - backend/scripts/ enthält operative Skripte: e2e_pipeline_test.py, run_e2e_real.py, final_production_check.py,
  test_master_scenario.py
  - scripts/ (Projekt-Root) enthält zusätzliche Standalone-Tests: test_live_pipeline.py, test_tenant_isolation.py,
  test_role_assignment.py

  Die conftest.py unter backend/tests/e2e/ ist besonders wichtig: Sie unterstützt bereits drei Umgebungen (DEV, STAGING, PRODUCTION)
  über die Umgebungsvariable TEST_ENV und enthält vollständige Fixtures für den gesamten Meeting-Lifecycle.

  1.3 Kubernetes Staging-Manifeste

  Das Staging-Verzeichnis infrastructure/kubernetes/staging/ enthält 20 Manifest-Dateien und deckt alle Backend-Dienste ab:
  PostgreSQL, Redis, RabbitMQ, MinIO, n8n, OnlyOffice, Backend-Deployment, Celery Worker/Beat, Traefik IngressRoutes.

  1.4 CI/CD-Pipeline

  Die Datei .github/workflows/e2e-tests.yml definiert eine dreistufige Pipeline: DEV-Tests via docker-compose, Staging-Deployment +
  vollständige E2E-Tests, und manuelle Production-Freigabe. Die Staging-Stufe läuft ausschließlich bei Pushes auf main.

  1.5 Externe Abhängigkeiten (Mocking-Strategie)

  Die Tests mocken alle externen API-Calls deterministisch:

  - Gladia (Transcription Service): mock_gladia Fixture
  - Mistral (PV-Generierung): mock_mistral_pv Fixture
  - Sentinel (LLM Service): mock_sentinel Fixture
  - n8n Webhooks: mock_n8n_action und mock_n8n_transcription Fixtures

  ---
  2. Lückenanalyse

  2.1 Fehlende Kubernetes-Manifeste im Staging-Verzeichnis

  Beim Vergleich von infrastructure/kubernetes/ (Production) mit infrastructure/kubernetes/staging/ fehlen im Staging folgende
  Dateien komplett:

  - services.yaml (definiert ClusterIP/NodePort Services für interne Kommunikation - kritisch, da die conftest.py interne DNS-Namen
  wie postgres-staging.meeting-automation-staging.svc.cluster.local verwendet)
  - traefik-deployment.yaml (Traefik selbst ist nicht deployed, nur IngressRoutes)
  - traefik-rbac.yaml (ServiceAccount, ClusterRole, ClusterRoleBinding für Traefik)
  - traefik-tls-secret.yaml und traefik-tls.yaml (TLS-Terminierung für staging.meeting-automate.tn)
  - network-policies.yaml (im Production vorhanden, Staging fehlt)
  - frontend-deployment.yaml und frontend-nginx-config.yaml (nur Backend deployed)
  - minio-pvc.yaml (PersistentVolumeClaim für MinIO-Storage fehlt)
  - n8n-pvc.yaml (PersistentVolumeClaim für n8n fehlt)

  Die fehlenden PVCs sind besonders kritisch, da die StatefulSets ohne Storage-Ansprüche nicht starten können.

  2.2 Fehlende GitHub Secrets

  Die e2e-tests.yml referenziert folgende Secrets, die in GitHub nicht definiert sein können wenn die Pipeline noch nicht läuft:

  - KUBE_CONFIG_STAGING: kubeconfig-Datei für den Staging-Cluster (Base64-kodiert)
  - STAGING_E2E_USER_EMAIL: E-Mail des dedizierten Test-Benutzers
  - STAGING_E2E_USER_PASSWORD: Passwort des dedizierten Test-Benutzers
  - MISTRAL_API_KEY_STAGING: Mistral API-Schlüssel (Staging)
  - GLADIA_API_KEY_STAGING: Gladia API-Schlüssel (Staging)
  - DOCKERHUB_TOKEN: Docker Hub Zugangstoken (für Image-Push)
  - KUBE_CONFIG_PRODUCTION: kubeconfig für Production (für Job 3)
  - PROD_ADMIN_EMAIL und PROD_ADMIN_PASSWORD: Production Smoke-Test-Credentials
  - SLACK_WEBHOOK_URL: Optional, für Deployment-Benachrichtigungen

  2.3 Inhaltliche Lücken in backend-secrets.yaml

  Die Datei infrastructure/kubernetes/staging/backend-secrets.yaml enthält Platzhalter-Werte:

  - MISTRAL_API_KEY und GLADIA_API_KEY sind als Shell-Variablen-Syntax eingetragen (${MISTRAL_API_KEY_STAGING}) - diese Syntax
  funktioniert nicht in Kubernetes-Manifesten, die Werte müssen zur Laufzeit via kubectl create secret --from-literal injiziert
  werden, wie es die CI/CD-Pipeline auch tut. Das Manifest selbst sollte keinen realen Secret-Wert enthalten.
  - E2E_TEST_USER_PASSWORD hat "placeholder-to-be-replaced-by-ci" - korrekt, aber muss in der Pipeline überschrieben werden.

  2.4 YAML-Syntaxfehler in der CI/CD-Pipeline

  In .github/workflows/e2e-tests.yml, Zeile 354, fehlt ein Leerzeichen: "-name:" statt "- name:". Dies verhindert eine korrekte
  YAML-Parsierung des letzten Steps im production-Deploy-Job.

  2.5 Konfig-Inkonsistenz: conftest.py vs. CI/CD-Pipeline

  Die E2E conftest.py erwartet für STAGING-Umgebung direkten DB-Zugriff via internem K8s-DNS
  (postgres-staging.meeting-automation-staging.svc.cluster.local). Die CI/CD-Pipeline überbrückt das mit kubectl port-forward auf
  localhost:5433 und setzt DATABASE_URL entsprechend. Das funktioniert nur wenn der GitHub Actions Runner Zugang zum Cluster hat -
  was wiederum KUBE_CONFIG_STAGING voraussetzt.

  2.6 Fehlende GitHub Environments-Konfiguration

  Die Workflow-Jobs referenzieren environment: staging und environment: production. Diese müssen in den GitHub Repository Settings
  unter Environments angelegt werden, sonst blockieren Protection Rules die Pipeline. Insbesondere environment: production sollte mit
   Required Reviewers konfiguriert werden.

  2.7 Pass-Rate-Inkonsistenz im Workflow

  Im e2e-tests.yml wird in der Kommentarzeile "≥95%" erwähnt, der tatsächliche Gate-Wert ist aber 85% (if [ $PASS_RATE -lt 85 ]). Das
   ist kein Fehler, aber eine Inkonsistenz die dokumentiert werden sollte.

  ---
  3. Umsetzungsplan

  Schritt 1: Staging-Cluster-Voraussetzungen prüfen (manuell)

  Überprüfe ob der Staging-Cluster läuft und erreichbar ist:

  - kubectl get nodes --kubeconfig kubeconfig-staging.txt ausführen (die Datei liegt bereits im Projekt-Root)
  - Namespace meeting-automation-staging prüfen oder anlegen
  - StorageClass-Verfügbarkeit prüfen (für PostgreSQL, MinIO, n8n PVCs)
  - Traefik-Verfügbarkeit im Cluster klären: Ist Traefik als Ingress-Controller bereits im Cluster installiert (z.B. via Helm) oder
  muss er aus den Manifesten deployed werden?

  Schritt 2: Fehlende Staging-Manifeste erstellen

  Basierend auf den Production-Pendants müssen die folgenden Dateien in infrastructure/kubernetes/staging/ ergänzt werden:

  - services.yaml: Alle ClusterIP-Services für PostgreSQL, Redis, RabbitMQ, MinIO, n8n, OnlyOffice, Backend - angepasst auf
  Staging-Namen (postgres-staging, redis-staging, etc.)
  - minio-pvc.yaml und n8n-pvc.yaml: PersistentVolumeClaims adaptiert für Staging-Namespace und kleinere Storage-Größen als
  Production
  - traefik-deployment.yaml und traefik-rbac.yaml: Nur wenn Traefik nicht cluster-weit bereits läuft
  - network-policies.yaml: Adaptiert für Staging-Namespace

  Die Production-Manifeste können als Ausgangsbasis dienen, erfordern aber Anpassungen bei Namespace-Namen, Service-Namen,
  Resource-Requests (Staging kann kleiner sein) und Storage-Größen.

  Schritt 3: GitHub Repository Settings konfigurieren (manuell, keine Automatisierung möglich)

  In GitHub unter Settings > Environments müssen zwei Environments angelegt werden:

  - staging: Keine Approval-Pflicht, aber Branch-Restriction auf main
  - production: Required Reviewers konfigurieren (mind. 1 Reviewer), Branch-Restriction auf main

  Anschließend unter Settings > Secrets and variables > Actions alle in Abschnitt 2.2 genannten Secrets anlegen. Die kubeconfig-Datei
   (KUBE_CONFIG_STAGING) muss vollständig Base64-kodiert als Secret gespeichert werden.

  Schritt 4: YAML-Syntaxfehler in e2e-tests.yml beheben

  In Zeile 354 den Fehler "-name:" zu "- name:" korrigieren. Dies ist der einzige Code-Fehler und blockiert den gesamten
  production-Deploy-Job.

  Schritt 5: Backend-Secrets.yaml bereinigen

  Die Platzhalter ${MISTRAL_API_KEY_STAGING} und ${GLADIA_API_KEY_STAGING} in der Datei
  infrastructure/kubernetes/staging/backend-secrets.yaml sollten durch leere Strings oder Kommentare ersetzt werden. Die echten Werte
   werden ausschließlich durch die CI/CD-Pipeline zur Laufzeit via kubectl create secret --from-literal injiziert. Secrets mit echten
   Werten gehören nicht in Git.

  Schritt 6: TLS-Zertifikat für staging.meeting-automate.tn

  Für HTTPS-Verbindungen zur Staging-URL muss ein TLS-Zertifikat vorhanden sein. Optionen:

  - cert-manager im Cluster mit Let's Encrypt (empfohlen, benötigt DNS-Eintrag)
  - Manuell erstelltes Zertifikat in traefik-tls-secret.yaml für Staging
  - Selbstsigniertes Zertifikat (dann PYTHONHTTPSVERIFY=0 in den Tests, was bereits gesetzt ist)

  Die Variable PYTHONHTTPSVERIFY=0 ist in der Pipeline bereits gesetzt, was auf selbstsignierte Zertifikate hinweist.

  Schritt 7: DNS-Eintrag für staging.meeting-automate.tn

  Der Hostname staging.meeting-automate.tn muss auf die externe IP des Staging-Clusters zeigen. Dies ist ein manueller DNS-Eintrag
  beim Domain-Registrar. Ohne diesen Eintrag schlagen alle Health-Checks in der Pipeline fehl.

  Schritt 8: E2E-Test-Benutzer in Staging-Datenbank sicherstellen

  Die Pipeline versucht den Test-Benutzer via /api/v1/auth/register anzulegen (idempotent). Beim allerersten Deployment ist das
  korrekt. Für den Fall, dass der Benutzer bereits existiert aber mit anderen Credentials, muss ein manueller Reset möglich sein. Ein
   Notfall-Skript backend/scripts/seed_users.py ist bereits im Projekt vorhanden und kann dafür verwendet werden.

  Schritt 9: Erst-Deployment manuell durchführen

  Beim allerersten Staging-Setup empfiehlt sich ein manuelles Deployment der Infrastructure-Manifeste in der richtigen Reihenfolge,
  bevor die CI/CD-Pipeline übernimmt:

  1. Namespace anlegen
  2. Alle Secrets anlegen (postgres-secrets, redis-secrets, rabbitmq-secrets, minio-secrets)
  3. StatefulSets starten (PostgreSQL, MinIO, RabbitMQ)
  4. Deployments starten (Redis, n8n, OnlyOffice, Backend, Celery Worker/Beat)
  5. Warten bis alle Pods Ready sind
  6. Datenbank-Migrationen manuell ausführen (alembic upgrade head im Backend-Pod)
  7. Services und IngressRoutes anwenden

  Schritt 10: Pipeline-Lauf validieren

  Nach Schritt 9 einen Test-Push auf main durchführen und die Pipeline beobachten. Die kritischen Prüfpunkte sind:

  - Job 1 (DEV): docker-compose E2E muss durchlaufen
  - Docker-Image muss erfolgreich nach Docker Hub gepusht werden
  - Job 2 (Staging): kubectl-Kontext muss konfigurierbar sein
  - Health-Check auf staging.meeting-automate.tn/health muss 200 zurückgeben
  - Port-Forward auf PostgreSQL muss funktionieren
  - pytest tests/e2e/ muss mit ≥85% Pass-Rate laufen

  ---
  4. Empfehlung: Priorisierte Action Items

  Priorität 1: Kritische Blocker (Pipeline kann nicht starten)

  - YAML-Syntaxfehler in e2e-tests.yml beheben (Zeile 354): Aufwand ca. 5 Minuten, blockiert den gesamten production-Deploy-Job
  - GitHub Secrets anlegen (KUBE_CONFIG_STAGING, DOCKERHUB_TOKEN, STAGING_E2E_USER_EMAIL, STAGING_E2E_USER_PASSWORD,
  MISTRAL_API_KEY_STAGING, GLADIA_API_KEY_STAGING): Aufwand ca. 30 Minuten, ohne diese kann die Pipeline nicht auf den Cluster
  zugreifen
  - GitHub Environments (staging, production) in Repository Settings anlegen: Aufwand ca. 15 Minuten, ohne diese blockieren die
  environment:-Direktiven den Workflow

  Priorität 2: Staging-Infrastruktur funktionsfähig machen

  - services.yaml für Staging erstellen: Aufwand ca. 1 Stunde, kritisch da interne K8s-DNS-Namen sonst nicht auflösen
  - PVCs für MinIO und n8n erstellen: Aufwand ca. 30 Minuten, StatefulSets starten ohne diese nicht
  - DNS-Eintrag für staging.meeting-automate.tn setzen: Aufwand ca. 15 Minuten beim Registrar, Health-Checks schlagen sonst fehl
  - Erst-Deployment manuell durchführen: Aufwand ca. 2-3 Stunden, einmaliger Aufwand

  Priorität 3: Vollständigkeit und Stabilität

  - TLS-Konfiguration für Staging klären (cert-manager vs. selbstsigniert): Aufwand ca. 1 Stunde
  - network-policies.yaml für Staging erstellen: Aufwand ca. 30 Minuten, nicht sofort kritisch aber Security-Best-Practice
  - Traefik-Deployment und RBAC für Staging prüfen/erstellen: Aufwand ca. 1 Stunde, abhängig von Cluster-Konfiguration
  - frontend-deployment.yaml für Staging erstellen: Aufwand ca. 1 Stunde, nur wenn E2E-Tests Frontend-Calls machen (aktuell nicht der
   Fall - alle Tests sind API-only)
  - Pass-Rate-Kommentar im Workflow auf korrekte 85% anpassen: Aufwand ca. 5 Minuten

  Priorität 4: Langfristige Verbesserungen

  - Production-Secrets anlegen (KUBE_CONFIG_PRODUCTION, PROD_ADMIN_EMAIL, PROD_ADMIN_PASSWORD): Aufwand ca. 30 Minuten, erst relevant
   wenn Production-Deployment aktiviert wird
  - SLACK_WEBHOOK_URL konfigurieren: Aufwand ca. 15 Minuten, für Deployment-Benachrichtigungen
  - Pass-Rate-Gate schrittweise auf 95% erhöhen wenn Test-Suite stabil ist

  ---
  5. Was kann aus bestehenden Artefakten übernommen werden

  Folgendes kann direkt wiederverwendet werden ohne neue Erstellung:

  - infrastructure/kubernetes/staging/: 20 Manifeste sind bereits vorhanden und müssen nur ergänzt werden
  - infrastructure/kubernetes/services.yaml: Kann als Vorlage für das fehlende Staging-Pendant dienen, Service-Namen und Namespace
  anpassen
  - infrastructure/kubernetes/minio-pvc.yaml und n8n-pvc.yaml: Direkte Vorlagen für Staging, Storage-Größen reduzieren
  - infrastructure/kubernetes/network-policies.yaml: Vorlage für Staging, Namespace-Selektor anpassen
  - infrastructure/kubernetes/traefik-deployment.yaml und traefik-rbac.yaml: Vorlage falls Traefik in Staging selbst deployed werden
  muss
  - backend/tests/e2e/conftest.py: Vollständig implementiert, keine Änderungen notwendig
  - backend/scripts/seed_users.py: Bereits vorhanden für manuellen Test-User-Reset
  - .github/workflows/e2e-tests.yml: Vollständig implementiert bis auf den Syntaxfehler in Zeile 354
  - kubeconfig-staging.txt: Datei liegt bereits im Projekt-Root und enthält die Staging-Cluster-Credentials

  Die kubeconfig-staging.txt im Projekt-Root ist der Inhalt, der als GitHub Secret KUBE_CONFIG_STAGING gespeichert werden muss.
  Achtung: Diese Datei sollte nicht ins Git-Repository committet werden (.gitignore prüfen).

  ---
  Zusammenfassung der Lücken nach Kritikalität

  - 3 kritische Blocker: YAML-Fehler, fehlende GitHub Secrets, fehlende Environments
  - 4 infrastrukturelle Lücken: services.yaml, PVCs, DNS, Erst-Deployment
  - 5 fehlende Manifest-Dateien: network-policies, Traefik-Stack, Frontend, PVCs
  - 1 inhaltliche Inkonsistenz: Pass-Rate-Kommentar im Workflow

  Die bestehende Codebasis ist sehr fortgeschritten. Der Großteil der Arbeit ist bereits erledigt. Die verbleibenden Aufgaben sind
  überwiegend Konfiguration und fehlende Manifest-Dateien, keine grundlegenden Architektur-Änderungen.
