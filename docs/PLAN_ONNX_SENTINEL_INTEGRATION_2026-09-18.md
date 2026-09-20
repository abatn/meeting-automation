# Integrationsplan: ONNX + Sentinel Fixes auf Staging

**Datum:** 2026-09-18  
**Ziel:** ONNX und Sentinel Fixes in der Pipeline auf Staging integrieren und testen  
**Architektur:** ARM64 (aarch64) — gleiche Plattform wie Production

---

## Zusammenfassung der Fixes

| # | Fix | Datei | Erwarteter Effekt |
|---|---|---|---|
| 1 | `enable_cpu_mem_arena=False` | `speaker_embedding_service.py` | ~3.5 GB weniger Peak |
| 2 | ONNX Reset vor Sentinel | `transcription_tasks.py` | Speicherfreigabe vor Sentinel |
| 3 | `malloc_trim(0)` nach Reset | `transcription_tasks.py` | glibc Fragmentierung reduzieren |
| 4 | llama-cpp-python updaten | `requirements.txt` | SIGABRT Fix |
| 5 | `n_ctx` reduzieren (2048→1024) | `sentinel_service.py` | SIGABRT Fix |
| 6 | GGML_NATIVE deaktivieren | `Dockerfile` | ARM64 Kompatibilität |

---

## Phase 1: ONNX Memory Fix (KRITISCH)

### 1.1 `enable_cpu_mem_arena=False`

**Datei:** `backend/app/services/speaker_embedding_service.py`

```python
# VORHER (Zeile 55-63):
providers = ["CPUExecutionProvider"]
self._session = ort.InferenceSession(ONNX_MODEL_PATH, providers=providers)

# NACHHER:
providers = ["CPUExecutionProvider"]
so = ort.SessionOptions()
so.enable_cpu_mem_arena = False  # ← OFFIZIELLER FIX (onnxruntime#11627)
so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
so.intra_op_num_threads = 1
self._session = ort.InferenceSession(ONNX_MODEL_PATH, sess_options=so, providers=providers)
```

**Erwarteter Effekt:**
- ONNX Peak: ~3749 MB → ~360 MB (ARM64)
- Kein OOM mehr bei ONNX Aktiv

### 1.2 ONNX Reset vor Sentinel

**Datei:** `backend/app/tasks/transcription_tasks.py`

```python
# NACH Zeile 421 (nach ONNX Reassignment):
onnx_reassign_duration = time.time() - stage_start
logger.info(f"TIMING: onnx_segment_reassignment ...")

# NEU EINFÜGEN:
# ONNX Session freigeben vor Sentinel-Ladung
if hasattr(speaker_embedding_service, '_session') and speaker_embedding_service._session:
    del speaker_embedding_service._session
    speaker_embedding_service._session = None
    speaker_embedding_service._initialized = False
    speaker_embedding_service._available = False
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    logger.info("ONNX session released before Sentinel load")

# Weiter mit Sentinel:
sentinel_start = time.time()
```

**Erwarteter Effekt:**
- ~3.5 GB ONNX-Speicher wird freigeben
- Sentinel hat genug Platz in 6Gi

---

## Phase 2: llama.cpp ARM64 Fix (KRITISCH)

### 2.1 llama-cpp-python updaten

**Datei:** `backend/requirements.txt`

```python
# VORHER:
llama-cpp-python==<alte_version>

# NACHHER:
llama-cpp-python>=0.3.0  # Mit PR #22327 (set_rows Error-Checking deaktiviert)
```

**Oder spezifische Version:**
```bash
pip install llama-cpp-python --upgrade
```

### 2.2 `n_ctx` reduzieren

**Datei:** `backend/app/services/sentinel_service.py`

```python
# VORHER (Zeile 95):
self.llm = Llama(
    model_path=self.model_path,
    n_ctx=2048,  # ← ZU GROSS für ARM64
    n_threads=1,
    verbose=False
)

# NACHHER:
self.llm = Llama(
    model_path=self.model_path,
    n_ctx=1024,  # ← REDUZIERT (spart ~50% KV-cache)
    n_threads=1,
    verbose=False
)
```

**Erwarteter Effekt:**
- KV-cache: ~9 MB/chunk → ~4.5 MB/chunk
- Reduziert Speicherdruck
- Verhindert Index-Überlauf in `set_rows`

### 2.3 GGML_NATIVE deaktivieren

**Datei:** `backend/Dockerfile`

```dockerfile
# VORHER:
RUN CMAKE_ARGS="-DLLAMA_NATIVE=ON" pip install llama-cpp-python

# NACHHER:
RUN CMAKE_ARGS="-DLLAMA_NATIVE=OFF" pip install llama-cpp-python
```

**Oder in Environment:**
```dockerfile
ENV GGML_NATIVE=OFF
```

**Erwarteter Effekt:**
- Verhindert ARM64 SIMD-Instruktionen die auf QEMU/in Docker nicht funktionieren

---

## Phase 3: Test-Plan auf Staging

### 3.1 Unit-Tests

```bash
# ONNX Memory Test
cd backend
python -c "
import onnxruntime as ort
import psutil
import os

# Test 1: Arena ON (default)
so_default = ort.SessionOptions()
sess_default = ort.InferenceSession('app/models/speaker_embeddings/ecapa-speaker-v1.onnx', sess_options=so_default)
mem_before = psutil.Process().memory_info().rss / 1024 / 1024
# ... run inference ...
mem_after = psutil.Process().memory_info().rss / 1024 / 1024
print(f'Arena ON: {mem_before:.0f} → {mem_after:.0f} MB (+{mem_after-mem_before:.0f} MB)')

# Test 2: Arena OFF
so_off = ort.SessionOptions()
so_off.enable_cpu_mem_arena = False
sess_off = ort.InferenceSession('app/models/speaker_embeddings/ecapa-speaker-v1.onnx', sess_options=so_off)
mem_before = psutil.Process().memory_info().rss / 1024 / 1024
# ... run inference ...
mem_after = psutil.Process().memory_info().rss / 1024 / 1024
print(f'Arena OFF: {mem_before:.0f} → {mem_after:.0f} MB (+{mem_after-mem_before:.0f} MB)')
"
```

### 3.2 Integration-Tests

```bash
# Test mit Consent-Client (f71675e5)
# 1. Meeting erstellen
# 2. Recording >30s
# 3. Prüfe: ONNX Status (Skip oder Aktiv)
# 4. Prüfe: Memory Peak < 4 GiB
# 5. Prüfe: Kein SIGABRT
# 6. Prüfe: Pipeline Complete
```

### 3.3 Last-Tests

```bash
# 5 Meetings gleichzeitig starten
# Monitor: kubectl top pods (alle 10s)
# Erwartung: Alle 5 complete, 0 Crashes
```

---

## Phase 4: Deployment auf Staging

### 4.1 Build

```bash
# Docker Image bauen
docker build -t meeting-automation-backend:fix-onnx-sentinel -f backend/Dockerfile backend/

# Multi-arch (ARM64 + AMD64)
docker buildx build --platform linux/amd64,linux/arm64 -t meeting-automation-backend:fix-onnx-sentinel backend/
```

### 4.2 Deploy

```bash
# Staging Namespace
kubectl set image deployment/celery-worker-pro \
  celery-worker=meeting-automation-backend:fix-onnx-sentinel \
  -n meeting-automation-staging

kubectl set image deployment/celery-worker \
  celery-worker=meeting-automation-backend:fix-onnx-sentinel \
  -n meeting-automation-staging

# Rollout abwarten
kubectl rollout status deployment/celery-worker-pro -n meeting-automation-staging
```

### 4.3 Verifikation

```bash
# Pods prüfen
kubectl get pods -n meeting-automation-staging -l app=celery-worker-pro

# Logs prüfen
kubectl logs -n meeting-automation-staging -l app=celery-worker-pro --tail=50 | grep -E 'ONNX|arena|SIGABRT|OOM'

# Memory prüfen
kubectl top pods -n meeting-automation-staging -l app=celery-worker-pro
```

---

## Erfolgskriterien

| Kriterium | Vorher | Nachher | Status |
|---|---|---|---|
| ONNX Peak (190 segs) | ~3749 MB | < 500 MB | ⏳ |
| Memory Peak (gesamt) | ~5878 MB | < 3000 MB | ⏳ |
| SIGABRT (≥2 Chunks) | 0% Success | 100% Success | ⏳ |
| Pipeline Complete | 50% (4/8) | 100% | ⏳ |
| OOMKilled | 2x | 0x | ⏳ |

---

## Risiken

| Risiko | Impact | Mitigation |
|---|---|---|
| llama-cpp-python Update bricht API | Hoch | Vorher API-Compat prüfen |
| n_ctx Reduktion verschlechtert Qualität | Niedrig | Test mit verschiedenen Chunks |
| ONNX Reset verursacht Re-Initialisierung | Niedrig | Lazy-Load Pattern beibehalten |
| GGML_NATIVE=OFF verlangsamt Inference | Niedrig | Benchmark vorher/nachher |

---

## Timeline

```
Tag 1: Phase 1 (ONNX Memory Fix)
  - enable_cpu_mem_arena=False implementieren
  - ONNX Reset + malloc_trim implementieren
  - Unit-Tests

Tag 2: Phase 2 (llama.cpp ARM64 Fix)
  - llama-cpp-python updaten
  - n_ctx reduzieren
  - GGML_NATIVE deaktivieren
  - Unit-Tests

Tag 3: Phase 3 (Integration-Tests)
  - Meetings mit Consent-Client testen
  - Memory-Monitoring
  - Crashes prüfen

Tag 4: Phase 4 (Deployment)
  - Docker Image bauen
  - Auf Staging deployen
  - Smoke-Tests

Tag 5: Verifikation
  - Last-Tests (5 Meetings)
  - Erfolgskriterien prüfen
  - Bei Erfolg → Production deployen
```

---

**Generated by Codebuff 🤖**  
**Date:** 2026-09-18T11:45:00+02:00
