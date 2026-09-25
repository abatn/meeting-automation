# Incident: Celery Kill-Reload-Schleife (Gratuit-Worker, Staging)

**Datum:** 2026-09-25 · **Cluster:** OCI ARM64 `instance-20260329-0846` (10.0.0.191), NS `meeting-automation-staging`
**Status:** Behoben (Fix deploy-fähig, Verifikation 15-min-Unhealthy-Fenster ausstehend)
**Impact:** ~30 Min. intermittierende Massen-Kills (5 Pods synchron, alle ~6 Min), Node 95 % CPU / 74 % RAM; Pipeline selbst betroffen (gather 135,08 s statt ~41 s Soll = G3-Zeit-Fehlschlag)

## Symptom

Alle Gratuit-Worker (`celery-worker-staging`) wurden **synchron** im ~6-Min-Rhythmus von Kubernetes gekillt und starteten neu; jeder Neustart lud das ONNX-Modell frisch (5 × ~500 m CPU), was die nächste Runde zusätzlich verlangsamte (Selbstverstärkung).

## Zeitleiste (Rohergebnisse, UTC)

| Zeit | Ereignis |
|---|---|
| vor dem Fix | Unhealthy-Count RabbitMQ-Readiness **3.749** (alter `timeoutSeconds`-Default 1 s); Beat-Liveness **131 Events / 21 Restarts**; Worker-Events `timed out after 30s → Killing` — **Problem existierte vor Commits `d86a9085`/`7b7d040e`** |
| 16:42 / 18:31 | Commits `d86a9085` (P1/P2/P3 + Probe-Entschärfungen 30→60 s etc.) und `7b7d040e` (Async-Tokenizer-Fix) gepusht, CI grün, Staging deployed |
| 20:58:47 | Test-Meeting „test nach migration 1" → `process_recording[4f48696a]` auf Pro-Worker |
| ~20:54–21:12 | KEDA skaliert Gratuit auf ~10 Pods (Backlog ≥ 5 Messages) → 10 × 1500 Mi-Requests + 3-Gi-Limits auf 23,5-Gi-Node → **OOMKilled (Exit 137)**, Pods `Pending` |
| 20:5x/21:0x | **Massen-Kills:** `8m53s` 5 Pods, `2m38s` 5 Ersatz-Pods — Abstand **6 m 15 s** = exakt `initialDelay 90 + 5 × period 60 = 390 s` |
| 21:06:33 | Pipeline `succeeded in 289.69s`, `pipeline_total=288.69s`, **0× RECORDING_FAILED**, `sentinel_chunks count=1` (P1+P3 funktional ✓); `sentinel_gather=135.08s` bei `prompt_tokens=579` → Soll 40,71 s → **+232 % → G3-Zeit FAIL (15-%-Regel) → STOP** |
| nach Meeting-Ende | Node beruhigt (15 % CPU / 36 % RAM), KEDA scale-to-zero, >28 min keine neuen Warnungen |

## Root Cause (3 Ebenen, alle belegt)

1. **Konstruktionsfehler seit `f375b42d` (02.07.2026):** Die Liveness-Probe jedes Pods war ein **flottenweiter** `celery inspect ping` (wartet auf ALLE Worker) und gleichzeitig der **Kill-Schalter**. Ein toter/verzögerter Nachbar ließ jeden gesunden Pod in die 60-s-Zeit laufen → alle gleichzeitig 5 Fehlschläge → synchroner Kill. Beweis: Event-Meldung enthält `celery@…pro…: OK…` (eigene Antwort ist da) **und** scheitert trotzdem am Timeout.
2. **Auslöser heute:** Test-Meeting → Queue-Backlog (`7 Messages/0 Consumer` + Alt-Task `47d3648c`) → KEDA `celery-worker-gratuit` (`maxReplicaCount: 10`, Trigger QueueLength 5 / CPU 80 %) skalierte auf ~10 → **10 × 3-Gi-Limits > 23,5-Gi-Node → OOM → tote Nachbarn**.
3. **Selbstverstärkung:** Jeder Neustart lädt ONNX frisch → CPU 95 % → nächste Ping-Runde noch langsamer → Wave-Periodizität.

**Nicht-Ursache:** Die heutigen Commits haben die Proben nur *geduldiger* gemacht (10→30 s, 30→60 s). Vor dem Deploy existierten dieselben Fehlschläge mit dem alten 30-s-Stand (Zahlen oben).

## Fix (angewandt, „Löschen ist verboten" — anpassen statt entfernen)

| Teil | Datei | Änderung |
|---|---|---|
| 1a | `staging/celery-worker-deployment.yaml` | Liveness → **self-targeted** `inspect ping -d celery@$(hostname) --timeout=10` (tötet nur bei Defekt *dieses* Pods); **Rundruf bleibt als readinessProbe** (`inspect ping --timeout=20`, Sichtbarkeit via Events, kein Kill) |
| 1b | `staging/celery-worker-pro-deployment.yaml` | dasselbe (Pro hatte denselben Flotten-Ping) |
| 2 | `staging/keda-scaledobjects.yaml` | `celery-worker-gratuit max 10 → 5` (5 × 1500 Mi ≈ 7,5 Gi passt), `celery-worker-pro max 10 → 3` |

## Verifikation (Pflicht nach Deploy)

1. 15 Min. **0** `Unhealthy`/`Killing` auf `celery-worker*` trotz Last = Schleife gebrochen
2. Node-RAM < 70 % bei skaliertem Gratuit-Fleet
3. Danach **G2-Idle-Lauf** (M1, N=650→607) auf ruhigem Node → P2/OMP sauber bewerten → G3-Zeitmesstung wiederholen

## Residuen (bewusst offen)

- **celery-beat-Liveness** nutzt weiterhin den Flotten-Ping (Beat hat keinen eigenen Worker-Namen — self-targeting würde fehlschlagen); derzeit stabil (0 Restarts)
- `FailedGetResourceMetric` (HPA `<unknown>`) — vorbestehende Metrics-API-Schwäche
- Queue-Backlog `transcription` (Alt-Messages) → sollte geleert/untersucht werden
- Produktion tabu — Fix nur Staging; Prod-Übertragung eigener Freigabe-/Prüfpfad
