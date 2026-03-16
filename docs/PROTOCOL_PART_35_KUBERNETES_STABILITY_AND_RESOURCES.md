PROTOKOLL: PART_35_KUBERNETES_STABILITY_AND_RESOURCES

Datum: 16.03.2026
Status: Abgeschlossen

## 🎯 ZIEL
Härtung der Kubernetes-Infrastruktur nach dem Umstieg auf Gladia V2. Optimierung des Ressourcenverbrauchs und Implementierung von Health-Checks für maximale Ausfallsicherheit.

## 🔧 TECHNOLOGIEN
- **Kubernetes Liveness/Readiness Probes**: Automatische Erkennung und Behebung von Dienstausfällen.
- **K8s Resource Limits**: Begrenzung von RAM/CPU zur Cluster-Stabilisierung.
- **Bash TCP Checks**: Intelligente Start-Synchronisation zwischen Workern und Brokern.

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1.  **Datenbank-Härtung (Postgres & RabbitMQ)**:
    *   Integration von `readinessProbe` mittels `pg_isready` (Postgres) und `rabbitmq-diagnostics` (RabbitMQ).
    *   Dies verhindert, dass abhängige Pods (Backend/Worker) eine Verbindung aufbauen, bevor die Datenbanken wirklich bereit sind.
2.  **Ressourcen-Optimierung (Gladia-Ready)**:
    *   Da die Transkription nun über Gladia Cloud läuft, wurden die RAM-Limits für den `celery-worker` auf 512Mi reduziert (vorher unbegrenzt, was lokal zu Swapping führte).
    *   Das `backend` wurde auf maximal 1Gi RAM begrenzt, um Speicher-Leaks im Cluster vorzubeugen.
3.  **Startup-Logik**:
    *   Der `sleep 10` Hack im Celery-Worker wurde durch eine `until timeout 2 bash -c '</dev/tcp/rabbitmq/5672'` Schleife ersetzt. Der Worker startet nun exakt in der Sekunde, in der RabbitMQ online ist.
4.  **API-Health**:
    *   Das Backend nutzt nun `/api/v1/auth/me` als Health-Check-Endpunkt, um sicherzustellen, dass nicht nur der Prozess läuft, sondern die API auch funktional antwortet.

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **WSL2 Ressourcen-Drosselung**: Docker Desktop neigt dazu, bei hohem RAM-Verbrauch instabil zu werden. Durch die festen K8s-Limits wird dieses Risiko minimiert.

## 🔗 ZUSAMMENHANG ZUM PROJEKT
Diese Maßnahmen transformieren das Kubernetes-Setup von einem reinen "Deployment-Entwurf" in ein robustes, produktionsreifes System.

## 📊 ERGEBNIS
Das System startet schneller, verbraucht weniger Ressourcen und verfügt über eine automatische Selbstheilung durch Kubernetes Probes.
