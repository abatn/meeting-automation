# Implementierungs-Prompt: Pipeline-Optimierung

**Erstellt:** 2026-08-24  
**Status:** 🟡 Bereit zur Implementierung  
**Voraussetzung:** Benchmarks verifiziert (siehe PIPELINE_OPTIMIZATION_STATUS_2026-08-23.md)

---

## ZWINGENDER PROMPT

```
Implementiere ONNX Pipeline-Optimierung mit verpflichtendem Rollback-Plan.

────────────────────────────────────────────────────────────────────
VORAUSSETZUNG (BEWIESEN)
────────────────────────────────────────────────────────────────────
ONNX intra_op_num_threads=1 ist 11.9× schneller als AUTO(8):
  - 300 Frames: 370ms vs 4415ms
  - Quelle: benchmark_beh_onnx300_both.py auf Production (169.58.83.32)

────────────────────────────────────────────────────────────────────
SCHRITT 1: CODE-ÄNDERUNG (1 Datei)
────────────────────────────────────────────────────────────────────

Datei: backend/app/services/speaker_embedding_service.py
Zeile: 63

VORHER:
    providers = ["CPUExecutionProvider"]
    self._session = ort.InferenceSession(ONNX_MODEL_PATH, providers=providers)

NACHHER:
    import onnxruntime as ort
    providers = ["CPUExecutionProvider"]
    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = int(os.environ.get("ONNX_NUM_THREADS", "1"))
    self._session = ort.InferenceSession(
        ONNX_MODEL_PATH, 
        providers=providers, 
        sess_options=sess_options
    )

────────────────────────────────────────────────────────────────────
SCHRITT 2: TESTS AUSFÜHREN
────────────────────────────────────────────────────────────────────

BEFEHL: cd backend && pytest tests/ -v --tb=short

ERWARTUNG: Alle Tests bestehen. Bei Fehler: NICHT deployen.

────────────────────────────────────────────────────────────────────
SCHRITT 3: COMMIT + PUSH
────────────────────────────────────────────────────────────────────

BEFEHL: 
  cd /home/opc/meeting-automation
  git add backend/app/services/speaker_embedding_service.py
  git commit -m "perf(onnx): intra_op_num_threads=1 via env var (11.9× speedup)"
  git push origin main

────────────────────────────────────────────────────────────────────
SCHRITT 4: CI VERIFIZIEREN
────────────────────────────────────────────────────────────────────

PRÜFE: https://github.com/[repo]/actions
ERWARTUNG: backend-test + frontend-test = GREEN

────────────────────────────────────────────────────────────────────
SCHRITT 5: DEPLOY PRODUCTION
────────────────────────────────────────────────────────────────────

BEFEHL:
  ssh root@169.58.83.32 
  cd /home/opc/meeting-automation
  ./scripts/deploy-prod/01-build-and-push.sh
  ./scripts/deploy-prod/02-deploy-backend.sh

────────────────────────────────────────────────────────────────────
SCHRITT 6: VERIFIKATION (PFICHT)
────────────────────────────────────────────────────────────────────

BEFEHL:
  ssh root@169.58.83.32 "kubectl logs -f deployment/celery-worker-pro | grep TIMING"

ERWARTUNG:
  TIMING: speaker_id_total duration=Xs (Ziel: <20s statt 106s)

────────────────────────────────────────────────────────────────────
SCHRITT 7: TEST-RECORDING
────────────────────────────────────────────────────────────────────

1. Meeting auf Production starten (Name: "test pipeline onnx fix")
2. Recording stoppen nach 30s
3. 5 Minuten warten
4. TIMING-Logs prüfen

ERWARTUNG:
  | Stage | Vorher | Nachher |
  |-------|--------|---------|
  | ONNX  | 106s   | <20s    |
  | Gesamt| 245s   | <160s   |

────────────────────────────────────────────────────────────────────
ROLLBACK-PLAN (BEI FEHLER)
────────────────────────────────────────────────────────────────────

FEHLER 1: Tests schlagen fehl
  → NICHT deployen
  → Code-Änderung rückgängig machen
  → Siehe: speaker_embedding_service.py Zeile 63

FEHLER 2: Deployment schlägt fehl
  → kubectl rollout undo deployment/celery-worker-pro
  → Siehe: infrastructure/kubernetes/production/celery-worker-pro-deployment.yaml

FEHLER 3: ONNX langsamer nach Fix
  → SessionOptions entfernen
  → Deploy rückgängig
  → Alten Code wiederherstellen

BEFEHL FÜR ROLLBACK:
  ssh root@169.58.83.32 "kubectl rollout undo deployment/celery-worker-pro -n meeting-automation"

────────────────────────────────────────────────────────────────────
LIEFERUNGSPFLICHT
────────────────────────────────────────────────────────────────────

Berichte am Ende:

┌─────────────────────────────────────────────────────────────────┐
│ SCHRITT    │ STATUS    │ BEWEIS                                │
├─────────────────────────────────────────────────────────────────┤
│ Code       │ ✅/❌     │ git diff + Tests                      │
│ Commit     │ ✅/❌     │ git log --oneline -1                  │
│ CI         │ ✅/❌     │ GitHub Actions URL                    │
│ Deploy     │ ✅/❌     │ kubectl get pods                      │
│ Verifikation│ ✅/❌    │ TIMING-Logs                           │
│ Test       │ ✅/❌     │ Recording-Ergebnis                   │
│ ROLLBACK   │ ✅/❌     │ Bei Bedarf: kubectl rollout undo      │
└─────────────────────────────────────────────────────────────────┘

NUR wenn ALLE 6 Schritte ✅: Optimierung ist ERFOLGREICH.
```

---

## ROLLBACK-CHECKLISTE

### Vor dem Deploy
- [ ] Tests bestanden
- [ ] CI green
- [ ] Backup vom aktuellen Deployment

### Nach dem Deploy
- [ ] TIMING-Logs zeigen Speedup
- [ ] Test-Recording erfolgreich
- [ ] Keine Fehler in Celery-Logs

### Bei Problemen
- [ ] Sofort: `kubectl rollout undo deployment/celery-worker-pro`
- [ ] Code: SessionOptions entfernen
- [ ] Commit: Revert mit `git revert`
