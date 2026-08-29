# Pipeline Crash Investigation — Production SIGSEGV

**Datum:** 2026-08-28 00:44 UTC  
**Betroffenes System:** Production (169.58.83.32)  
**Schweregrad:** P0 (Pipeline funktioniert nicht)  
**Status:** Offen

---

## Was passiert ist

Test Meeting "test pipeline" auf Production. Pipeline stürzt bei Sentinel LLM mit **SIGSEGV (Signal 11)** ab.

### Fehler
```
[2026-08-28 00:44:29] ERROR: Process 'ForkPoolWorker-8' pid:25 exited with 'signal 11 (SIGSEGV)'
[2026-08-28 00:44:29] ERROR: WorkerLostError('Worker exited prematurely: signal 11 (SIGSEGV) Job: 38.')
```

### TIMING (Vor dem Crash)
| Schritt | Dauer | Staging |
|---------|-------|---------|
| S3 Download | 0.28s | 0.02s |
| Gladia | 6.99s | 6.24s |
| ONNX Init | 0.00s | 3.03s |
| FFmpeg | 27.29s | 2.96s |
| ONNX Embed | **115.10s** | **27.26s** |
| Speaker ID | **143.08s** | **30.44s** |
| Sentinel | **CRASH** | 55.92s |

### Root Cause Hypothesen
1. **k3s CPU 70%** → Wenig CPU für ONNX/Sentinel → Memory Pressure → SIGSEGV
2. **GOGC nicht gesetzt** → Go GC erzeugt Memory Pressure auf dem Node
3. **Sentinel Model zu groß** für verfügbares Memory
4. **ONNX Runtime** instabil bei hoher CPU-Last

---

## Untersuchungs-Prompt für Agent

```
Untersuche den SIGSEGV Crash der Production Pipeline (169.58.83.32):

1. PRÜFE den aktuellen k3s CPU/Load:
   - ps aux | grep k3s | grep -v grep
   - uptime
   - cat /proc/loadavg

2. PRÜFE den Sentinel Model Download:
   - Prüfe ob das Modell im Pod korrekt heruntergeladen wurde
   - kubectl exec -n meeting-automation celery-worker-pro-* -- ls -la /app/models/
   - Prüfe Modellgröße (erwartet: 900MB-1.5GB)

3. PRÜFE Memory-Druck:
   - free -h
   - cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree"
   - Prüfe ob OOM-Killer aktiv war: dmesg | grep -i oom | tail -5

4. VERGLEICHE mit Staging (158.180.18.110):
   - Gleicher Befehl auf Staging ausführen
   - CPU/Load/Memory vergleichen

5. PRÜFE ob das Sentinel Model auf Prod korrekt ist:
   - md5sum /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
   - Vergleiche mit Staging

6. ERSTELLE eine Tabelle mit allen Unterschieden zwischen Staging und Production die den Crash erklären könnten.

7. EMPFEHLE Fixes mit konkreten kubectl-Befehlen.
```

---

## Bekannte Unterschiede (aus YAML-Analyse)

| Komponente | Staging | Production | Risiko |
|-----------|---------|------------|--------|
| k3s CPU | 18% | **70%** | 🔴 KRITISCH |
| k3s Load | 1.01 | **4.80** | 🔴 KRITISCH |
| LiveKit Server CPU | 500m/1000m | **100m/500m** | 🟡 |
| LiveKit Server RAM | 512Mi/1024Mi | **256Mi/512Mi** | 🟡 |
| Backend ephemeral-storage | 200Mi/1Gi | **FEHLT** | 🟡 |
| SKIP_RECORDING_RATE_LIMIT | "true" | **FEHLT** | 🟡 |
| GOGC | nicht gesetzt | **nicht gesetzt** | 🟡 |
| GOMEMLIMIT | nicht gesetzt | **nicht gesetzt** | 🟡 |

---

## Erwartete TIMING-Vergleich (Staging vs Production)

| Schritt | Staging | Production | Faktor |
|---------|---------|------------|--------|
| S3 Download | 0.02s | 0.28s | 14x |
| Gladia | 6.24s | 6.99s | 1.1x |
| ONNX Init | 3.03s | 0.00s | - |
| FFmpeg | 2.96s | 27.29s | **9.2x** |
| ONNX Embed | 27.26s | **115.10s** | **4.2x** |
| Speaker ID | 30.44s | **143.08s** | **4.7x** |
| Sentinel | 55.92s | **CRASH** | ∞ |
| **Gesamt** | **113.27s** | **CRASH** | - |

---

## Nächste Schritte

1. **Sofort:** GOGC=50 + GOMEMLIMIT=1500Mi auf Prod setzen (k3s.service.env)
2. **Sofort:** LiveKit Server Resources erhöhen (500m/1000m)
3. **Test:** Pipeline erneut ausführen nach den Fixes
4. **Dokumentation:** Ergebnis in docs/ dokumentieren
