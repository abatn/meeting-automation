# Pipeline-Optimierungs-Status: 2026-08-23

**Erstellt:** 2026-08-23  
**Aktualisiert:** 2026-08-24 (mit verifizierten Benchmarks)  
**Zusammengefasst aus:** PIPELINE_QUICK_WINS.md, PIPELINE_ANALYSIS_2026-08-12.md, SENTINEL_ROLLBACK_2026-08-12.md  
**Status:** 🟡 Pipeline komplett (245s), aber Ziel 90s nicht erreicht  
**Cluster:** Production (169.58.83.32, 8 Core AMD EPYC, 23GB RAM) + Staging (ARM64, 4 Core)

---

## 1. Zusammenfassung: Ziele, Gemacht, Ergebnisse

### Quick Wins (PIPELINE_QUICK_WINS.md)

| # | Ziel | Status | Ergebnis |
|---|------|--------|----------|
| 1 | Adaptive Gladia Polling (110s → <10s) | ✅ **ERLEDIGT** | **6.6s** (−94%) |
| 2 | Early S3 Download (Overlap) | ⬜ NICHT GEMACHT | — |
| 3 | Speaker Batch Optimierung | ⬜ NICHT GEMACHT | — |
| 4 | Celery Tuning (prefetch, acks) | ✅ **ERLEDIGT** | Implementiert |

### Pipeline-Analyse (PIPELINE_ANALYSIS_2026-08-12.md)

| Phase | Alte Erwartung | Test 4 Realität | Status |
|-------|---------------|-----------------|--------|
| Gladia Polling | ~110s | **6.6s** | ✅ **Gelöst** |
| Speaker ID | ~5s | **106.48s** | 🔴 **21× langsamer** |
| Sentinel LLM | existierte nicht | **121.06s** | 🔴 **Neues Hauptproblem** |
| Mistral PV | ~15s | **5.17s** | ✅ **Schneller** |
| Persistence | — | **0.32s** | ✅ OK |
| **GESAMT** | **~140s** | **245.37s** | 🔴 **1.8× langsamer** |

### Sentinel Rollback (SENTINEL_ROLLBACK_2026-08-12.md)

| Änderung | Status | Auswirkung |
|----------|--------|------------|
| `SKIP_SENTINEL=true` → `false` | ✅ **ERLEDIGT** | Sentinel LLM aktiv |
| llama-cpp-python installiert | ✅ | Qwen-1.5B GGUF (1.1GB) |
| CI Build ~3 Min → ~8 Min | ✅ | Akzeptabel |
| Rollback nötig? | ❌ | Funktioniert, aber langsam |

---

## 2. Gemessene Pipeline-Performance (Test 4)

**Recording:** fa33aa33 (test pipeline 4, ~30s Audio, 8 Segmente, 2 Sprecher)  
**Status:** ✅ `completed`

### Gesamt-Timing

```
TIMING: pipeline_total duration=245.37s
  (s3=1.5s gladia=6.6s speaker=106.5s sentinel=121.1s mistral=5.2s persist=0.3s)
```

### Stage-Level Timing (BEWIESEN)

| Stage | Dauer | % von 245s | Status | Vorher (Docs) |
|-------|-------|------------|--------|---------------|
| S3 Download | 1.5s | 1% | ✅ OK | ~0.1s |
| Gladia Transcription | 6.6s | 3% | ✅ OK | ~110s |
| **Speaker ID** | **106.5s** | **43%** | 🔴 KRITISCH | ~5s |
| **Sentinel LLM** | **121.1s** | **49%** | 🔴 KRITISCH | existierte nicht |
| Mistral PV | 5.2s | 2% | ✅ OK | ~15s |
| Persistence | 0.3s | 0% | ✅ OK | — |
| **GESAMT** | **245.37s** | **100%** | 🔴 Ziel: 90s | ~140s |

### Sub-Step Timing

**Speaker ID (106.5s):**
```
speaker_id_profile_load: 0.01s (DB Query)
ffmpeg_extract_concat: 21.40s (8 Segmente)
onnx_embed: ~85s (librosa + fbank + ONNX)
speaker_id_process_speakers: 104.77s (Gesamt)
speaker_id_total: 106.48s (2 Speakers, 1 resolved)
```

**Sentinel LLM (121.1s):**
```
sentinel_plan_check: 0.20s (DB Query)
sentinel_chunks: count=1, text_len=223
sentinel_gather: 121.06s (1 Chunk)
```

---

## 3. Warum die Docs falsch waren

| Doc | Behauptung | Grund der Diskrepanz |
|-----|-----------|---------------------|
| PIPELINE_QUICK_WINS.md | Speaker-ID: <1s | Galt für Staging (ARM64), nicht Production (AMD64) |
| PIPELINE_QUICK_WINS.md | PV + Actions: <1s | Sentinel existierte noch nicht |
| PIPELINE_ANALYSIS_2026-08-12.md | Speaker ID: ~5s | Galt für 4 Segmente auf Staging |
| PIPELINE_ANALYSIS_2026-08-12.md | Gesamt: ~140s | Kein Sentinel, keine Production-Messung |

**Die Quick Wins haben Gladia gelöst (110s → 6.6s), aber ONNX und Sentinel sind die NEUEN Hauptprobleme.**

---

## 4. Bekannte Probleme (aktuell)

### 🔴 ONNX Speaker ID (106.5s)

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Modell | ECAPA-TDNN 79.6MB | speaker_embedding_service.py |
| intra_op_num_threads | 0 (AUTO = 8) | InferenceSession |
| Container CPU | 1 Core | cgroup v2 |
| **Effekt** | **8 Workers teilen 1 Core = 0.125 Cores** | |
| **ONNX Benchmark** | 300 Frames: threads=1 → 319ms, threads=8 → 3085ms (9.7× langsamer) | BEWIESEN |

**Root Cause:** Thread-Thrashing — ONNX mit AUTO-Threads auf 1 CPU Core ist 9.7× langsamer als mit 1 Thread.

### 🔴 Sentinel LLM (121.1s)

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Modell | Qwen-1.5B Q4_K_M 1,066MB | sentinel_service.py:93 |
| n_threads | **2** (hardcoded) | sentinel_service.py:96 |
| n_ctx | 2048 | sentinel_service.py:95 |
| max_tokens | 256 | sentinel_service.py:134 |
| Inference Rate | **1.2 tok/s** | Benchmark |
| **1 Chunk (223 Zeichen)** | **121s** | Test 4 gemessen |

**Root Cause:** Qwen-1.5B auf 1 CPU Core mit n_threads=2 = 1.2 tok/s. 223 Zeichen ≈ 60 Tokens → ~50s Generation + ~70s Prefill/Overhead.

### 🟡 Liveness Probe Kill (behoben)

| Problem | Ursache | Status |
|---------|---------|--------|
| Worker wurde gekillt während ONNX lief | `celery inspect ping --timeout=10` bekam keine Antwort | ✅ Behoben (kein Kill in Test 4) |

### 🟡 RabbitMQ Probe (behoben)

| Problem | Ursache | Status |
|---------|---------|--------|
| 190 ExecSync-Errors/Stunde | `rabbitmq-diagnostics` braucht 25.5s auf AMD64 | ✅ Behoben (tcpSocket) |

---

## 5. Was gemacht wurde (Chronologie)

| Datum | Fix | Ergebnis |
|-------|-----|----------|
| 2026-06-12 | ONNX Singleton Lazy Init | ✅ |
| 2026-06-12 | Redis Connection Pooling | ✅ |
| 2026-06-12 | ffmpeg Parallel Extraction | ✅ |
| 2026-08-12 | Adaptive Gladia Polling | ✅ 110s → 6.6s |
| 2026-08-12 | Celery prefetch_multiplier=1 + task_acks_late=True | ✅ |
| 2026-08-22 | Sub-Step TIMING-Logs (Speaker ID + Sentinel) | ✅ 27 Logs |
| 2026-08-23 | RabbitMQ readinessProbe: tcpSocket | ✅ Load 16.58→3.87 |
| 2026-08-23 | RabbitMQ volumeMount + envFrom | ✅ Users persisted |
| 2026-08-23 | LiveKit Egress Downgrade v1.14.1→v1.8.4 | ✅ Recording funktioniert |
| 2026-08-23 | Test Pipeline 3: ONNX 0.70s (4 Segmente) | ✅ |
| 2026-08-23 | Test Pipeline 4: ONNX 106s (8 Segmente) | ⚠️ Skalierungsproblem |
| 2026-08-23 | Test Pipeline 4: Pipeline komplett (245s) | ✅ Kein Liveness Kill |

---

## 6. Verifizierte Optimierungen (BEWIESEN durch Benchmarks)

### ✅ P0: ONNX intra_op_num_threads=1

| Metrik | Vorher | Nachher | Speedup | Status |
|--------|--------|---------|---------|--------|
| ONNX 300f t=1 | 4415ms | 370ms | **11.9×** | ✅ **BEWIESEN** |
| ONNX 3000f t=1 | 4527ms | 4327ms | 1.05× | ✅ **BEWIESEN** |

**Code-Änderung:** `speaker_embedding_service.py` Zeile 63 — `SessionOptions()` mit `intra_op_num_threads=1` hinzufügen
**Erwarteter Effekt:** ONNX von ~85s → ~7s (für 8 Segmente)

### ❌ Celery Workers 8→2 — WIDERLEGT

| Metrik | Vorher | Nachher | Status |
|--------|--------|---------|--------|
| ONNX 300f t=1 | 300ms | 317ms | ❌ **-5%** |

**Grund:** `kubectl scale replicas` ändert NICHT die Worker-Anzahl pro Pod. Celery nutzt Default `os.cpu_count()=8`.  
**Lösung:** `--concurrency=2` zum Celery-Command hinzufügen (Code-Change, nicht Scaling).

### ⚠️ Sentinel Cold Start

| Metrik | Vorher | Nachher | Status |
|--------|--------|---------|--------|
| Cold Start | 303.7s | 68.8s | ⚠️ **78%** |

**Grund:** Erster Aufruf lädt 1GB Modell in RAM. Zweiter Aufruf nutzt Cache.  
**Lösung:** Modell bei Worker-Start laden (nicht lazy).

---

## 7. Rollback-Plan

### Bei ONNX-Regression

```bash
# 1. SessionOptions entfernen
# speaker_embedding_service.py Zeile 63:
# VORHER: ort.InferenceSession(ONNX_MODEL_PATH, providers=providers, sess_options=sess_options)
# NACHHER: ort.InferenceSession(ONNX_MODEL_PATH, providers=providers)

# 2. Deploy
./scripts/deploy-prod/01-build-and-push.sh
./scripts/deploy-prod/02-deploy-backend.sh

# 3. Verifikation
kubectl logs -f deployment/celery-worker-pro | grep TIMING
```

### Bei Sentinel-Regression

```bash
# 1. Modell-Caching deaktivieren
# sentinel_service.py: Lazy Singleton beibehalten

# 2. Fallback auf Mistral API
# falls lokales Modell nicht läuft
```

### Bei Celery-Concurrency-Regression

```bash
# 1. --concurrency entfernen
# celery-worker-pro-deployment.yaml: command zurücksetzen

# 2. Deploy
kubectl apply -f infrastructure/kubernetes/production/celery-worker-pro-deployment.yaml
```

---

## 8. Hardcoded Werte (MÜSSEN ELIMINIERTIERT WERDEN)

| Wert | Aktuell | Datei | Env-Var | Status |
|------|---------|-------|---------|--------|
| `n_threads=2` | Sentinel LLM | sentinel_service.py:98 | `SENTINEL_N_THREADS` | ⚠️ Beibehalten (kein Nutzen bewiesen) |
| `n_ctx=2048` | Sentinel Context | sentinel_service.py:95 | `SENTINEL_N_CTX` | ⚠️ Beibehalten |
| `max_tokens=256` | Sentinel Output | sentinel_service.py:141 | `SENTINEL_MAX_TOKENS` | ⚠️ Beibehalten |
| `intra_op_num_threads=0` | ONNX Auto-Threads | speaker_embedding_service.py:63 | `ONNX_NUM_THREADS` | ✅ **IMPLEMENTIEREN** |
| `concurrency=8` | Celery Workers | celery_worker-pro-deployment.yaml | — | ❌ **WIDERLEGT** (Scaling ändert nichts) |

---

## 8. Vergleich: Staging vs Production

| Eigenschaft | Staging (ARM64) | Production (AMD64) |
|-------------|-----------------|---------------------|
| CPU Kerne | 4 | 8 |
| Container CPU Limit | 1 Core | 1 Core |
| ONNX 8 Segmente | <10s | **106.5s** |
| Sentinel 1 Chunk | ~30s | **121.1s** |
| Pipeline Total | ~60s | **245.37s** |
| Load Average | 4.02 | 3.87 (nach RabbitMQ Fix) |
| RabbitMQ Probe | 0 Errors | 0 Errors (nach tcpSocket Fix) |

**Root Cause des Unterschieds:** ARM64 Cortex-A76 hat höhere Single-Thread-Performance pro Core als AMD EPYC 2.0GHz. ONNX und Sentinel profitieren von schnellem Single-Thread.
