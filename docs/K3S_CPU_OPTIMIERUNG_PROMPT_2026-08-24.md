# k3s CPU-Optimierung — Agent-Prompt

**Quelle:** docs/K3S_TUNING_PLAN_2026-08-20.md (Schritt 7: k3s CPU Optimierung)
**Status:** OFFEN — 4 Massnahmen geplant, keine umgesetzt
**Regel:** "Löschen ist verboten" — nichts entfernen, nur optimieren

---

## KONTEXT (100% bewiesene Fakten)

Production Server: 169.58.83.32 (AMD64, 8 Cores, 23GB RAM)
k3s Version: v1.36.2+k3s1
Container Runtime: containerd 2.3.2-k3s2

Aktuelle CPU-Last:
- k3s server: 86.4% CPU (Hauptproblem)
- containerd: 27% CPU
- prometheus: 26% CPU
- Load Average: 4.10 / 5.00 / 5.85 (trending down)
- Gesamt: 103% auf 8 Kernen

Warum ist k3s bei 86%?
- 67 CRDs × ~8 Operator-Scopes = 518 Watch-Connections (Event-Filterung ~30% CPU)
- 153,999 Lease PUTs (etcd-Write ~35% CPU)
- API-Server + Scheduler + Controller-Manager + etcd in 1 Go-Prozess

Vergleichbare k3s-Cluster mit 40 Pods:
- Erwartete k3s CPU: 10-30%
- Unsere k3s CPU: 86.4% (2.9-8.6x zu hoch)

---

## LOESUNG (4 Massnahmen aus K3S_TUNING_PLAN)

### Massnahme P1: Longhorn CRDs reduzieren
- Aktuell: 23 Longhorn CRDs
- Ziel: ~10 CRDs
- Effekt: -13 Watches, -2-3% CPU
- Schwierigkeit: Mittel

### Massnahme P2: Velero CRDs prüfen
- Aktuell: 13 Velero CRDs, nur 1 Schedule
- Effekt: -13 Watches, -1-2% CPU
- Schwierigkeit: Leicht

### Massnahme P3: CNPG reconcile-Intervall erhöhen
- Aktuell: 15s
- Ziel: 60s
- Effekt: -12 API-Requests/min, -2% CPU
- Schwierigkeit: Leicht

### Massnahme P4: Prometheus Scrape-Intervall erhöhen
- Aktuell: 30s
- Ziel: 60s
- Effekt: -1% CPU
- Schwierigkeit: Leicht

Maximale Einsparung: P1+P2+P3 = ~7% CPU (85% → ~78%)

---

## AUFGABEN

### Aufgabe 1: Longhorn CRDs analysieren
Führe aus:
```
ssh root@169.58.83.32 "kubectl get crd | grep longhorn"
```
Erwartung: 23 CRDs
Frage: Welche CRDs können entfernt werden ohne Funktionsverlust?

### Aufgabe 2: Velero CRDs analysieren
Führe aus:
```
ssh root@169.58.83.32 "kubectl get crd | grep velero"
ssh root@169.58.83.32 "kubectl get schedules.velero.io -n velero"
ssh root@169.58.83.32 "kubectl get backups.velero.io -n velero"
```
Erwartung: 13 CRDs, 1 Schedule, 23 Backups
Frage: Welche CRDs werden nicht gebraucht?

### Aufgabe 3: CNPG reconcile-Intervall finden
Führe aus:
```
ssh root@169.58.83.32 "kubectl get configuration -n cnpg-system -o yaml"
```
Frage: Wo ist updateInterval gesetzt? Aktueller Wert?

### Aufgabe 4: Prometheus Scrape-Intervall finden
Führe aus:
```
ssh root@169.58.83.32 "kubectl get configmap -n monitoring prometheus-server -o yaml | grep scrapeInterval"
```
Frage: Aktueller scrapeInterval?

### Aufgabe 5: HPA-Fehler analysieren
Führe aus:
```
ssh root@169.58.83.32 "kubectl describe hpa keda-hpa-backend -n meeting-automation | tail -10"
```
Erwartung: "FailedGetResourceMetric" — pods.metrics.k8s.io nicht erreichbar
Frage: Wie viele Fehler pro Stunde? (Antwort: 239/h = 10982/46h)

### Aufgabe 6: KEDA ScaledObjects prüfen
Führe aus:
```
ssh root@169.58.83.32 "kubectl get scaledobjects --all-namespaces"
```
Frage: Welche ScaledObjects brauchen KEDA? Welche funktionieren?

---

## LIEFERUNG

Für jede Massnahme:
1. Exakter Befehl der ausgeführt wurde
2. Ergebnis des Befehls
3. Bewertung: UMSETZBAR / NICHT UMSETZBAR / TEILWEISE
4. Risiko: NIEDRIG / MITTEL / HOCH
5. CI/CD-Pfad: Git → CI → kubectl apply

Finale Tabelle:
| Massnahme | Vorher | Nachher | Einsparung | Umsetzbar? |
|-----------|--------|---------|------------|------------|
| P1: Longhorn CRDs | 23 | ? | ?% | ? |
| P2: Velero CRDs | 13 | ? | ?% | ? |
| P3: CNPG Intervall | 15s | ? | ?% | ? |
| P4: Prometheus | 30s | ? | ?% | ? |
| GESAMT | 86% | ? | ?% | ? |

---

## REGELN

1. "Löschen ist verboten" — nichts entfernen, nur optimieren
2. Jede Zahl muss gemessen werden (run_terminal_command)
3. Keine Annahmen, keine Extrapolation
4. CI/CD-Pfad: Git commit → CI → Deploy
5. Rollback-Plan für jede Änderung
