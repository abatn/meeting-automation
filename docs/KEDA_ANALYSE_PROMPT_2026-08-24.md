# KEDA CPU-Überlastungs-Analyse

**Erstellt:** 2026-08-24
**Problem:** Load 8.27/8 Kerne = 103%, k3s server 86% CPU
**Ursache:** HPA Reconcile-Loop → 480 Fehler/Stunde

---

## HINTERGRUND

KEDA (Kubernetes Event-driven Autoscaling) wurde auf Production installiert um Celery Workers dynamisch zu skalieren.

**Was KEDA macht:**
- RabbitMQ Queue-Länge als Trigger für Pod-Scaling
- Scale-to-Zero wenn keine Tasks
- Dynamisches Scaling basierend auf Last

**Was auf Production schiefgegangen ist:**
1. KEDA metrics-apiserver ist nicht erreichbar
2. pods.metrics.k8s.io API fehlt (kein metrics-server auf k3s)
3. HPA (keda-hpa-backend, keda-hpa-livekit-egress) versucht alle 15s Metriken → 480 Fehler/Stunde
4. Jeder Fehler erzeugt k3s reconcile-loop → 86% CPU

**Bekanntes Problem (docs/AUTOSCALING_ARCHITECTURE_2026-08-14.md):**
- Cross-Namespace NetworkPolicy: KEDA (namespace: keda) kann RabbitMQ (namespace: meeting-automation) nicht erreichen
- Auf Staging funktioniert es, auf Production nicht (andere Calico-Implementierung)

---

## AUFGABE

Untersuche die CPU-Überlastung auf Production (169.58.83.32).

**Fakten:**
- Load Average: 8.27 auf 8 Kernen
- k3s server: 86% CPU
- 480 HPA-Fehler/Stunde (KEDA metrics-apiserver nicht erreichbar)
- KEDA wurde installiert für dynamisches Celery-Worker-Scaling
- Cross-Namespace NetworkPolicy verhindert KEDA→RabbitMQ Verbindung

**Untersuche:**
1. Welche KEDA-Pods laufen und warum ist metrics-apiserver defekt?
2. Welche HPAs verursachen die 480 Fehler?
3. Werden die KEDA ScaledObjects auf Production überhaupt gebraucht?
4. Welche Funktionen gehen verloren wenn KEDA entfernt wird?
5. Was ist die einfachste Lösung um die CPU-Last zu senken?

**Finde die Ursache und die beste Lösung.**
