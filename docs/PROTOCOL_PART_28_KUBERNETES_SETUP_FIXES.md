PROTOKOLL: PART_28_KUBERNETES_SETUP_FIXES

Datum: 09.03.2026
Status: Abgeschlossen
🎯 ZIEL
Vollständige Übernahme des Docker-Compose Setups (`setup-system.sh`) in die neue Kubernetes-Umgebung (Docker Desktop). Behebung von Netzwerk- und Konfigurationsproblemen, um die Funktionalität (Login, Daten-Seeding) innerhalb des Clusters sicherzustellen.

🔧 TECHNOLOGIEN
- Kubernetes (Deployments, StatefulSets, Services, ConfigMaps)
- Nginx (Reverse Proxy & DNS Resolution)
- SOPS (Secret Management)
- Alembic & Python (Datenbank-Setup)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. **Ressourcen-Management**:
   - Festgestellt, dass Docker Compose und Kubernetes gleichzeitig das RAM-Limit von Docker Desktop sprengen.
   - `docker compose down` ausgeführt, um Ressourcen für Kubernetes freizugeben.
   - Die Kubernetes `Deployments` wurden angepasst, um die lokalen Images mit `imagePullPolicy: Never` zu verwenden, was den `ImagePullBackOff` Fehler behob.

2. **System-Initialisierung (`setup-system.sh` zu K8s portiert)**:
   - Die manuellen Setup-Schritte aus `setup-system.sh` wurden direkt in den Kubernetes-Pods (`kubectl exec`) ausgeführt:
     - Alembic Datenbank-Migrationen verifiziert (`alembic stamp head`).
     - n8n Hilfstabelle `n8n_meetings` in Postgres angelegt.
     - Testbenutzer (u.a. `dg@meeting.tn`) über `scripts/seed_users.py` in die Datenbank geladen.
     - Der S3-Bucket `meeting-recordings` wurde über `scripts/create_s3_bucket.py` im MinIO-Pod erstellt.

3. **Frontend Nginx & DNS-Fix**:
   - Problem: Der Frontend-Container nutzte hartkodiert den Docker-internen DNS (`127.0.0.11`), wodurch das Backend in Kubernetes nicht gefunden wurde.
   - Lösung: Erstellung einer `ConfigMap` (`frontend-nginx-config.yaml`), die `resolver kube-dns.kube-system.svc.cluster.local` für das Frontend überschreibt. Diese wurde per Volume in den Pod gemountet.

4. **Backend CORS-Security Update**:
   - Problem: Login-Requests von `http://127.0.0.1:3000` (nötig zur Umgehung von WSL2-Netzwerkproblemen) wurden vom Backend blockiert.
   - Lösung: Die Kubernetes `backend-config.yaml` wurde aktualisiert, um `http://127.0.0.1:3000` in die `CORS_ORIGINS` aufzunehmen. Das Backend-Deployment wurde neu gestartet.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **"CrashLoopBackOff" bei MinIO**: Der Kommando-Aufruf im StatefulSet war falsch (`server` statt `minio server`). Dies wurde im Manifest korrigiert.
- **"Login failed from catch block"**: Verursacht durch die falsche Nginx-DNS-Auflösung und restriktive CORS-Regeln. Durch ConfigMap und Umgebungsvariablen gelöst, ohne das ursprüngliche Docker-Image zu modifizieren.

🔗 ZUSAMMENHANG ZUM PROJEKT
Diese Phase schließt die Vorbereitung für eine produktionsnahe Kubernetes-Umgebung ab. Alle Container, die in `docker-compose.yml` liefen, laufen nun stabil in K8s unter Verwendung der in Phase 1 (Part 27) eingerichteten verschlüsselten SOPS-Secrets.

📊 ERGEBNIS
Alle 11 Pods (inklusive Celery-Worker und Beat) sind im Status `Running`. Der Login mit den geseedeten Daten ist erfolgreich, Dashboards laden korrekt (HTTP 200). Das System ist nun bereit für den nächsten Schritt: Netzwerksegmentierung.
