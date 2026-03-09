PROTOKOLL: PART_29_KUBERNETES_SETUP_SCRIPT

Datum: 09.03.2026
Status: Abgeschlossen
🎯 ZIEL
Erstellung eines automatisierten Setup-Skripts (`setup-kubernetes.sh`) für die Kubernetes-Umgebung, das die Funktionalität von `setup-system.sh` (Docker Compose) abbildet und gleichzeitig die Sicherheit des SOPS-Verschlüsselungsschlüssels (`age` key) automatisiert gewährleistet.

🔧 TECHNOLOGIEN
- Bash Scripting
- SOPS & age
- Kubernetes (`kubectl apply`, `kubectl exec`, `kubectl wait`)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. **Schlüssel-Management & Sicherheit**:
   - Skript prüft auf Existenz einer ungesicherten `key.txt` im Projektordner.
   - Falls gefunden, wird der Inhalt an den Systemstandard `~/.config/sops/age/keys.txt` angehängt.
   - Setzen von strikten Rechten (`chmod 600`) zum Schutz vor unbefugtem Zugriff.
   - Löschung der ungesicherten `key.txt` aus dem Projekt-Root, um versehentliche Commits ins Git-Repository zu verhindern.
2. **Automatisierter Kubernetes-Start**:
   - Entschlüsseln und Anwenden aller `*-secrets.yaml` mittels SOPS.
   - Anwenden von Namespaces, Services, ConfigMaps, StatefulSets und Deployments in der korrekten, abhängigen Reihenfolge.
   - Verwendung von `kubectl wait` zur Synchronisierung, bevor abhängige Skripte ausgeführt werden.
3. **Automatisierte Initialisierung**:
   - Ausführung der Alembic-Migrationen im Backend-Pod.
   - Ausführung der n8n-Hilfstabellen-Kreation im Postgres-Pod.
   - Seeding der Testbenutzer und Kreation des S3-Buckets.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **SOPS Key Pfad**: SOPS benötigt standardmäßig die Umgebungsvariable `SOPS_AGE_KEY_FILE` oder sucht im System-Verzeichnis. Das Skript setzt diese Variable dynamisch und verlagert den Key an den sicheren Ort, was die Benutzererfahrung (kein manuelles `export` mehr nötig) und Sicherheit massiv verbessert.

🔗 ZUSAMMENHANG ZUM PROJEKT
Dieses Skript konsolidiert alle manuellen Befehle aus Phase 1 (Secret Management) und Phase 1.5 (Kubernetes Fixes) in einen robusten, wiederholbaren Prozess für die lokale Entwicklung und CI/CD-Pipelines.

📊 ERGEBNIS
Das System kann nun mit einem einzigen Befehl (`./setup-kubernetes.sh`) vollständig und sicher in Kubernetes gestartet werden. Der Verschlüsselungsschlüssel ist permanent und sicher im Benutzerprofil hinterlegt.
