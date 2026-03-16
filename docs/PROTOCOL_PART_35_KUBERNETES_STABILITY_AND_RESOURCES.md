PROTOKOLL: PART_35_KUBERNETES_STABILITY_AND_RESOURCES

Datum: 16.03.2026
Status: Abgeschlossen

## 🎯 ZIEL
Härtung der Kubernetes-Infrastruktur nach dem Umstieg auf Gladia V2. Optimierung des Ressourcenverbrauchs und Implementierung von Health-Checks für maximale Ausfallsicherheit. Behebung von Startproblemen bei kritischen Diensten (RabbitMQ).

## 🔧 TECHNOLOGIEN
- **Kubernetes Liveness/Readiness Probes**: Automatische Erkennung und Behebung von Dienstausfällen.
- **K8s Resource Limits**: Begrenzung von RAM/CPU zur Cluster-Stabilisierung.
- **Bash TCP Checks**: Intelligente Start-Synchronisation zwischen Workern und Brokern.
- **RabbitMQ `rabbitmq-diagnostics`**: Offizielles Tool zur Gesundheitsprüfung.

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1.  **Datenbank-Härtung (Postgres & RabbitMQ)**:
    *   Integration von `readinessProbe` mittels `pg_isready` (Postgres) und `rabbitmq-diagnostics` (RabbitMQ).
    *   Dies verhindert, dass abhängige Pods (Backend/Worker) eine Verbindung aufbauen, bevor die Datenbanken wirklich bereit sind.
    *   **Korrektur des RabbitMQ `readinessProbe` Timeouts**: Erhöhung der `initialDelaySeconds` auf `30`, `periodSeconds` auf `20` und `timeoutSeconds` auf `15` in `rabbitmq-statefulset.yaml`. Dies behebt den `Connection refused` Fehler und die Neustart-Schleifen des RabbitMQ-Pods auf Docker Desktop.
2.  **Ressourcen-Optimierung (Gladia-Ready)**:
    *   Da die Transkription nun über Gladia Cloud läuft, wurden die RAM-Limits für den `celery-worker` auf 512Mi reduziert (vorher unbegrenzt, was lokal zu Swapping führte).
    *   Das `backend` wurde auf maximal 1Gi RAM begrenzt, um Speicher-Leaks im Cluster vorzubeugen.
3.  **Startup-Logik**:
    *   Der `sleep 10` Hack im Celery-Worker wurde durch eine `until timeout 2 bash -c '</dev/tcp/rabbitmq/5672'` Schleife ersetzt. Der Worker startet nun exakt in der Sekunde, in der RabbitMQ online ist.
4.  **API-Health**:
    *   Das Backend nutzt nun den öffentlichen `/health` Endpunkt für seine Health-Checks (vorher `/api/v1/auth/me`), um `401 Unauthorized` Fehler bei den Probes zu vermeiden.
5.  **n8n Workflow Initialisierung (Bekanntes Problem)**:
    *   Feststellung, dass n8n nach einem Cluster-Reset seine Workflows vergisst und diese manuell über die n8n UI (http://localhost:5678) neu importiert und aktiviert werden müssen. Die CLI-Importe sind aufgrund von ID-Konflikten nicht zuverlässig.

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **RabbitMQ `readinessProbe` Timeout**: Standard-Kubernetes-Timeout von 1s war zu kurz für `rabbitmq-diagnostics check_running` auf Docker Desktop. Lösung: Erhöhung von `timeoutSeconds` auf 15s im `rabbitmq-statefulset.yaml`.
- **WSL2 Ressourcen-Drosselung**: Docker Desktop neigt dazu, bei hohem RAM-Verbrauch instabil zu werden. Durch die festen K8s-Limits wird dieses Risiko minimiert.
- **Backend Health-Check 401**: Verwendung eines geschützten Endpunkts für Health-Checks führte zu Fehlstarts. Lösung: Umstellung auf den ungeschützten `/health` Endpunkt.
- **n8n Workflow-Management**: Automatischer Import der Workflows per CLI ist unzuverlässig nach Reset. Lösung: Aktuell manueller Import über n8n UI empfohlen.

## 🔗 ZUSAMMENHANG ZUM PROJEKT
Diese Maßnahmen transformieren das Kubernetes-Setup von einem reinen "Deployment-Entwurf" in ein robustes, produktionsreifes System. Sie beheben kritische Startup-Probleme und erhöhen die Gesamtstabilität erheblich.

## 📊 ERGEBNIS
Das System startet schneller, verbraucht weniger Ressourcen und verfügt über eine automatische Selbstheilung durch Kubernetes Probes. Die Live-Aufnahme und KI-Verarbeitung (Gladia V2) funktionieren nun einwandfrei, sobald n8n Workflows manuell initialisiert wurden.
