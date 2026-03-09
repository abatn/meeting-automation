PROTOKOLL: PART_31_TRAEFIK_RATE_LIMITING

Datum: 09.03.2026
Status: Abgeschlossen
🎯 ZIEL
Einführung eines dedizierten API-Gateways zur Abwehr von DDoS-Angriffen (Zero-Trust Security). Implementierung von Traefik als Ingress-Controller inklusive Traffic-Management und striktem Rate-Limiting für Authentifizierungs- und API-Endpunkte gemäß der ISO 27001 Roadmap.

🔧 TECHNOLOGIEN
- Traefik v3 (API Gateway & Ingress Controller)
- Kubernetes CRDs (`IngressRoute`, `Middleware`)
- Kubernetes RBAC (`ServiceAccount`, `ClusterRole`, `ClusterRoleBinding`)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. **CRD-Installation**: Traefik-spezifische Custom Resource Definitions für fortgeschrittenes Routing und Middlewares installiert.
2. **RBAC-Konfiguration**: `traefik-rbac.yaml` erstellt, um Traefik die benötigten Leserechte für Services und IngressRoutes im Cluster zu gewähren.
3. **Traefik-Deployment**: `traefik-deployment.yaml` erstellt. Der Proxy wurde als `LoadBalancer`-Service auf den Ports 80, 443 und 8080 (Admin) hochgefahren.
4. **Rate Limiting Middlewares**: `traefik-middlewares.yaml` definiert zwei Schutz-Regeln:
   - `rate-limit-general`: Erlaubt durchschnittlich 50 Requests/Sekunde (Burst 100) für Standard-APIs und das Frontend.
   - `rate-limit-auth`: Ein weitaus restriktiveres Limit (5 Requests/Sekunde, Burst 10) für den Endpunkt `/api/v1/auth`, um Brute-Force-Angriffe abzuwehren.
5. **Modernes Routing**: Der klassische Nginx-Ingress wurde entfernt und durch eine Traefik `IngressRoute` (`traefik-ingressroute.yaml`) ersetzt. Die Route verknüpft dynamisch die konfigurierten Middlewares mit den Endpunkten.
6. **Automatisierung**: Das Startskript `setup-kubernetes.sh` wurde aktualisiert, um die alten Nginx-Ressourcen durch den neuen Traefik-Stack zu ersetzen.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Veraltete Ingress-Ressourcen**: Der Wechsel von klassischem `networking.k8s.io/v1 Ingress` auf Traefiks mächtigeres `IngressRoute` CRD erforderte das vorherige saubere Löschen der alten Nginx-Regeln, um Routing-Konflikte (Port 80) auf dem Host zu vermeiden.

🔗 ZUSAMMENHANG ZUM PROJEKT
Damit ist der Meilenstein "Parallel: API Gateway & Rate Limiting" vollständig abgeschlossen. Das System ist nun vor Überlastung, DDoS und simplen Brute-Force-Attacken auf API-Ebene geschützt.

📊 ERGEBNIS
Traefik fungiert nun als zentraler Einstiegspunkt (Edge Router). Jeglicher Traffic nach außen wird reglementiert, bevor er das Frontend oder Backend erreicht.
