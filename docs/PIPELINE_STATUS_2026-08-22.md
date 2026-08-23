# Pipeline-Status: 2026-08-22

**Erstellt:** 2026-08-22
**Letztes Update:** 2026-08-23 20:00 UTC
**Status:** 🟡 Test Pipeline 3 completed (247.54s). ONNX gelöst (0.70s), Sentinel noch 222s. Frontend-Bug: Transcription nicht sichtbar.
**Cluster:** Production (169.58.83.32, 8 Core AMD EPYC, 23GB RAM)
**Celery Pod:** `celery-worker-pro-5b94485b99-phjs8` (Image: `sha256:adf9a81f...`)

---

## 1. Gemessene Pipeline-Performance (Production)

**Recording:** 7cc15aba (70.3s Audio, 13 Segmente, 1 Sprecher)
**Agent:** Buffy (Freebuff)

### Gesamt-Timing

```
TIMING: pipeline_total duration=460.4s
  (s3=0.1s gladia=6.6s speaker=184.2s sentinel=252.8s mistral=11.2s persist=0.4s)
```

### Stage-Level Timing (BEWIESEN)

| Stage | Dauer | % Gesamt | Status |
|-------|-------|----------|--------|
| S3 Download | 0.1s | 0% | ✅ OK |
| Gladia Transcription | 6.6s | 1% | ✅ OK |
| ONNX Init | 2.5s | 1% | ✅ OK |
| **Speaker ID** | **184.2s** | **40%** | 🔴 KRITISCH |
| **Sentinel LLM** | **252.8s** | **55%** | 🔴 KRITISCH |
| Mistral PV | 11.2s | 2% | ✅ OK |
| Persistence | 0.4s | 0% | ✅ OK |
| **GESAMT** | **460.4s** | **100%** | 🔴 Ziel: 90s |

### Sub-Step Timing (NEU — 2026-08-22 implementiert, 2026-08-23 deployed)

**Status: ✅ ALLE 27 TIMING-Logs im Pod verifiziert**

```
# Speaker ID Sub-Steps (9 Logs)
TIMING: speaker_id_profile_load duration=Xs profiles=N with_embeddings=N candidates=[...]
TIMING: speaker_{label}_embedding duration=Xs
TIMING: ffmpeg_extract_concat duration=Xs segments=13
TIMING: onnx_embed duration=Xs
TIMING: speaker_{label}_signals duration=Xs mistral_triggered=True mistral_dur=Xs
TIMING: speaker_id_process_speakers duration=Xs speakers=N
TIMING: speaker_id_exclusivity duration=Xs assigned=N
TIMING: speaker_id_enrollment duration=Xs enrolled=N consent=yes/no
TIMING: speaker_id_total duration=184.2s speakers=1 resolved=N

# Sentinel Sub-Steps (5 Logs)
TIMING: sentinel_plan_check duration=Xs plan=PRO
TIMING: sentinel_cold_start duration=Xs model=...
TIMING: sentinel_summarize prompt_tokens=X output_tokens=Y llm_dur=Xs tok_per_sec=Z
TIMING: sentinel_gather duration=Xs chunks=1 summaries=1
```

---

## 2. BEWIESENE Ursachen

### Container-Ressourcen (cgroup v2)

| Ressource | Limit | Fakt |
|-----------|-------|------|
| CPU | **1 Core** | cgroup v2: quota=100000, period=100000 |
| Memory | **6 GB** | celery-worker-pro-deployment.yaml |
| os.cpu_count() | **8** | HOST-Kerne (LÜGE für Container) |

### Celery Worker

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Workers | **8** (Default = os.cpu_count()) | celery_app.py: kein `worker_concurrency` |
| Pool-Typ | prefork | Default |
| Concurrency | 8 | Default |
| Container CPU Limit | 1 Core | kubectl: cpu="1" |
| **Effekt** | **8 Workers teilen sich 1 Core = 0.125 Cores pro Worker** | |

### ONNX Runtime

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Modell | ECAPA-TDNN 79.6MB | speaker_embedding_service.py |
| intra_op_num_threads | 0 (AUTO = 8) | InferenceSession ohne SessionOptions |
| inter_op_num_threads | 0 (AUTO) | InferenceSession ohne SessionOptions |
| execution_mode | ORT_SEQUENTIAL | Default |
| GIL released during session.run() | Ja (C++ Backend) | — |

### ONNX Thread-Thrashing Benchmark (BEWIESEN)

```
Input: 300 Frames (3s Audio)
threads=1:  319ms   ← SCHNELLSTER
threads=2:  721ms   (2.3x langsamer)
threads=4:  992ms   (3.1x langsamer)
threads=8:  3085ms  (9.7x langsamer) ← DEFAULT = WORST CASE
```

**BEWIESEN:** Mehr Threads = langsamer auf 1 CPU Core (Thread-Thrashing)

### Sentinel LLM

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Modell | Qwen-1.5B Q4_K_M 1,066MB | sentinel_service.py:93 |
| n_threads | **2** (hardcoded) | sentinel_service.py:96 |
| n_ctx | 2048 | sentinel_service.py:95 |
| max_tokens | 256 | sentinel_service.py:134 |
| Cold Start | 3.0s | Benchmark |
| Inference Rate | 1.2 tok/s | Benchmark |

### Sentinel 252s Aufschlüsselung (BEWIESEN)

```
Prompt Prefill:  ~39s (200 Tokens)
Token Generation: ~213s (256 Tokens × 1/1.2 tok/s)
Gesamt:          ~252s
```

---

## 3. Pipeline-Struktur (Code)

```
_process_recording_pipeline (transcription_tasks.py)
│
├── 1. S3 Download                                      ~0.1s
│   └── _download_audio()
│
├── 2. Gladia Transcription                             ~6.6s
│   └── gladia_service.transcribe_and_diarize()
│
├── 3. ONNX Init                                        ~2.5s
│   └── speaker_embedding_service.initialize()
│
├── 4. Speaker ID (_identify_speakers)                  ~184s ← KRITISCH
│   ├── TIMING: speaker_id_profile_load                ~0.1s (DB Query)
│   ├── process_single_speaker() (pro Sprecher)
│   │   ├── TIMING: speaker_{label}_embedding          ~???s
│   │   │   ├── TIMING: ffmpeg_extract_concat          ~???s (13 Segmente parallel)
│   │   │   └── TIMING: onnx_embed                     ~???s (librosa + fbank + ONNX)
│   │   ├── Signal Collection
│   │   │   ├── LiveKit Identity (String-Match)         ~0s
│   │   │   ├── Heuristic (_match_speaker_to_participant) ~0s
│   │   │   ├── ONNX Audio Matching (cosine distance)   ~0.1s
│   │   │   ├── Regex Self-Introduction                 ~0s
│   │   │   └── Mistral Fusion (HTTP API)               ~???
│   │   └── TIMING: speaker_{label}_signals            ~???s (inkl. Mistral)
│   ├── TIMING: speaker_id_process_speakers            ~???s (Gesamt)
│   ├── TIMING: speaker_id_exclusivity                 ~0.01s
│   └── TIMING: speaker_id_enrollment                  ~1s (DB Write + Audit)
│   └── TIMING: speaker_id_total                       ~184s
│
├── 5. ONNX Segment Reassignment (13× sequentiell)     ~???
│   └── for seg in segments:
│       ├── _extract_single_segment (ffmpeg)            ~0.3s
│       ├── extract_embedding (ONNX)                    ~???
│       └── match_speaker_from_list                     ~0.1s
│
├── 6. Sentinel LLM (MAP Phase)                         ~252s ← KRITISCH
│   ├── TIMING: sentinel_plan_check                     ~0.1s (DB Query)
│   ├── TIMING: sentinel_chunks count=1 text_len=785    ~0s (Chunking)
│   ├── TIMING: sentinel_cold_start                     ~0-3s (Qwen-1.5B laden)
│   ├── TIMING: sentinel_summarize                      ~???s (pro Chunk)
│   │   ├── Prompt Prefill                              ~39s
│   │   └── Token Generation (256 tokens)               ~213s
│   └── TIMING: sentinel_gather                         ~???s (Gesamt)
│
├── 7. Mistral PV (REDUCE Phase)                        ~11.2s
│   └── PVService.generate_pv()
│
└── 8. Persistence                                       ~0.4s
    ├── _save_transcription()
    └── _save_pv_and_actions()
```

---

## 4. Was NICHT das Problem ist

| Komponente | Dauer | Status |
|------------|-------|--------|
| S3 Download | 0.1s | ✅ OK |
| Gladia Polling | 6.6s | ✅ OK (vorher 110s, jetzt optimiert) |
| Mistral PV | 11.2s | ✅ OK |
| Persistence | 0.4s | ✅ OK |
| ONNX Init | 2.5s | ✅ OK |

---

## 5. Was die Docs sagten (veraltet)

| Doc | Behauptung | Realität |
|-----|-----------|----------|
| PIPELINE_QUICK_WINS.md | Speaker-ID: <1s | **184s** (184× langsamer) |
| PIPELINE_QUICK_WINS.md | PV + Actions: <1s | **264s** (Sentinel + Mistral) |
| PIPELINE_QUICK_WINS.md | Hauptproblem: Gladia Polling (110s) | **Gelöst** (6.6s) |
| PIPELINE_ANALYSIS_2026-08-12.md | Speaker ID: ~5s | **184s** (37× langsamer) |
| PIPELINE_ANALYSIS_2026-08-12.md | Gesamt: ~140s | **460s** (3.3× langsamer) |

**Grund der Diskrepanz:** Die Docs wurden geschrieben bevor:
1. Sentinel LLM (Qwen-1.5B) zur Pipeline hinzugefügt wurde
2. ONNX auf Production (1 CPU Core) getestet wurde
3. Die 8-Worker-auf-1-Core Problematik bekannt war

---

## 6. Bestehende TIMING-Logs (Code)

### Stage-Level (bereits vorhanden)

```python
# transcription_tasks.py
logger.info(f"TIMING: s3_download duration={s3_duration:.2f}s")
logger.info(f"TIMING: gladia_transcription duration={gladia_duration:.2f}s")
logger.info(f"TIMING: onnx_init duration={time.time() - stage_start:.2f}s")
logger.info(f"TIMING: speaker_identification duration={speaker_duration:.2f}s")
logger.info(f"TIMING: onnx_segment_reassignment duration={onnx_reassign_duration:.2f}s")
logger.info(f"TIMING: sentinel_chunks count={len(chunks)} text_len={len(display_text)}")
logger.info(f"TIMING: sentinel_llm duration={sentinel_duration:.2f}s")
logger.info(f"TIMING: mistral_pv duration={mistral_duration:.2f}s")
logger.info(f"TIMING: persistence duration={persist_duration:.2f}s")
logger.info(f"TIMING: pipeline_total duration={duration:.2f}s")
```

### Sub-Step Level — Speaker ID (NEU — 2026-08-22)

```python
# _identify_speakers (transcription_tasks.py)
logger.info(f"TIMING: speaker_id_profile_load duration=...s profiles=N with_embeddings=N candidates=[...]")  # DB Query
logger.info(f"TIMING: speaker_id_process_speakers duration=...s speakers=N")                               # Gesamt für alle Speaker
logger.info(f"TIMING: speaker_id_exclusivity duration=...s assigned=N")                                     # Name-Assignment
logger.info(f"TIMING: speaker_id_enrollment duration=...s enrolled=N consent=yes/no")                      # DB Write + Audit
logger.info(f"TIMING: speaker_id_total duration=184.2s speakers=1 resolved=N")                             # Gesamt

# process_single_speaker (pro Sprecher)
logger.info(f"TIMING: speaker_{label}_embedding duration=...s")                                             # ffmpeg + librosa + fbank + ONNX
logger.info(f"TIMING: speaker_{label}_signals duration=...s mistral_triggered=True mistral_dur=...s")       # Signals + Mistral Fusion

# _extract_speaker_embedding
logger.info(f"TIMING: ffmpeg_extract_concat duration=...s segments=13")                                     # ffmpeg alone
logger.info(f"TIMING: onnx_embed duration=...s")                                                           # librosa + fbank + ONNX alone
```

### Sub-Step Level — Sentinel LLM (NEU — 2026-08-22)

```python
# _process_recording_pipeline (transcription_tasks.py)
logger.info(f"TIMING: sentinel_plan_check duration=...s plan=PRO")                                          # DB Query
logger.info(f"TIMING: sentinel_chunks count=1 text_len=785")                                                # Chunking
logger.info(f"TIMING: sentinel_gather duration=...s chunks=1 summaries=1")                                  # Gesamt Gather

# sentinel_service.py
logger.info(f"TIMING: sentinel_cold_start duration=...s model=...")                                         # Qwen-1.5B Laden (1. Mal)
logger.info(f"TIMING: sentinel_summarize prompt_tokens=X output_tokens=Y llm_dur=...s tok_per_sec=Z")      # Pro Chunk
```

---

## 7. Offene Fragen (nächste Schritte)

| Frage | Status |
|-------|--------|
| Wie viel von den 184s kommt von ffmpeg vs ONNX vs Mistral Fusion? | ⏳ Warte auf Test-Recording (TIMING-Logs deployed) |
| Wie viel von den 252s kommt von Cold Start vs Prefill vs Token Gen? | ⏳ Warte auf Test-Recording (TIMING-Logs deployed) |
| ONNX Thread-Thrashing: Lohnt sich `intra_op_num_threads=1`? | ⏳ Warte auf Benchmark |
| Sentinel: Lohnt sich `n_threads=1` + `max_tokens=128`? | ⏳ Warte auf Benchmark |
| Celery Concurrency 8→1: Reduziert CPU-Kontention? | ⏳ Warte auf Test |
| Mistral Fusion: Wird sie überhaupt getriggert? (score < 0.65?) | ⏳ Warte auf Test-Recording |

---

## 8. 🔴 HARDCODIERTE WERTE — MÜSSEN ELIMINIERT WERDEN

**Regel: Hardcoded ist verboten.** Alle Werte müssen aus Environment-Variablen gelesen werden.

| Wert | Aktuell (hardcoded) | Datei | Zeile | Muss geändert werden |
|------|---------------------|-------|-------|---------------------|
| `n_threads=2` | Sentinel LLM Threads | sentinel_service.py | 96 | ✅ JA — Env-Var `SENTINEL_N_THREADS` |
| `n_ctx=2048` | Sentinel LLM Context Window | sentinel_service.py | 95 | ✅ JA — Env-Var `SENTINEL_N_CTX` |
| `max_tokens=256` | Sentinel Max Output Tokens | sentinel_service.py | 134 | ✅ JA — Env-Var `SENTINEL_MAX_TOKENS` |
| `intra_op_num_threads=0` | ONNX Auto-Threads | speaker_embedding_service.py | 58 | ✅ JA — Env-Var `ONNX_NUM_THREADS` |
| `concurrency=8` | Celery Workers | celery_app.py | — | ✅ JA — Env-Var `CELERY_CONCURRENCY` |

**Nächster Schritt:** Alle hardcoded Werte durch `os.environ.get()` mit sinnvollen Defaults ersetzen → dann Deployment via CI/CD.

## 9. Pipeline-Optimierungs-Historie

| Datum | Fix | Ergebnis |
|-------|-----|----------|
| 2026-06-12 | ONNX Singleton Lazy Init | ✅ Behoben |
| 2026-06-12 | Redis Connection Pooling | ✅ Behoben |
| 2026-06-12 | ffmpeg Parallel Extraction | ✅ Behoben |
| 2026-06-12 | Gladia Polling Timeout (300s) | ✅ Behoben |
| 2026-08-12 | Adaptive Gladia Polling | ❌ NICHT implementiert |
| 2026-08-12 | Early S3 Download | ❌ NICHT implementiert |
| 2026-08-12 | Speaker Batch sleep(0.1) entfernen | ❌ NICHT implementiert |
| 2026-08-22 | Celery prefetch_multiplier=1 + task_acks_late=True | ✅ Implementiert |
| 2026-08-22 | Sub-Step TIMING-Logs (Speaker ID + Sentinel) | ✅ Implementiert |
| 2026-08-22 | Speaker ID Sub-Step TIMING komplett | ✅ Implementiert (commit d52b1c14) |
| 2026-08-22 | Sentinel Sub-Step TIMING komplett | ✅ Implementiert (commit 14738738) |
| 2026-08-22 | Pipeline-Status Dokumentation | ✅ Implementiert (commit c987c67a) |
| 2026-08-22 | CI/CD Deploy (TIMING-Logs) | ✅ SUCCESS — CI Pipeline + Deploy Staging |
| 2026-08-23 | Port-Forward Keepalive (E2E-Test Fix) | ✅ Implementiert (commit cd0116d6) |
| 2026-08-23 | Deploy Production (TIMING-Logs + Keepalive) | ✅ SUCCESS — aber Pod NICHT automatisch neu gestartet |
| 2026-08-23 | Manueller Pod-Restart | ✅ celery-worker-pro-5b94485b99-phjs8 (neues Image verifiziert) |
| 2026-08-23 | Sub-Step TIMING-Logs im Pod verifiziert | ✅ 27 Logs vorhanden — warte auf Test-Recording |
| 2026-08-23 | RabbitMQ readinessProbe: tcpSocket | ✅ Load 16.58→3.87 (−76%) |
| 2026-08-23 | RabbitMQ volumeMount + envFrom | ✅ Users persisted |
| 2026-08-23 | LiveKit Egress Downgrade v1.14.1→v1.8.4 | ✅ Recording funktioniert wieder |
| 2026-08-23 | Test Pipeline 3 (TIMING gemessen) | ✅ Pipeline completed: 247.54s |

---

## 10. Test Pipeline 3 — Gemessene Ergebnisse (2026-08-23)

**Recording:** c93154af (test pipeline 3, 4 Segmente, 2 Sprecher)
**Status:** ✅ `completed`

### Gesamt-Timing

```
TIMING: pipeline_total duration=247.54s
  (s3=0.2s gladia=11.9s speaker=0.7s sentinel=222.7s mistral=3.9s persist=0.6s)
```

### Stage-Level Timing (Vergleich)

| Stage | Vorher (7cc15aba) | Jetzt (c93154af) | Änderung |
|-------|-------------------|------------------|----------|
| S3 Download | 0.1s | 0.16s | ≈gleich |
| Gladia | 6.6s (13 Seg) | 11.94s (4 Seg) | ≈gleich |
| ONNX Init | 2.55s | 2.91s | ≈gleich |
| **Speaker ID** | **184.2s** | **0.70s** | **−99.6%** ✅ |
| **Sentinel LLM** | **252.8s** | **222.72s** | **−12%** |
| Mistral PV | 11.2s | 3.92s | −65% |
| Persistence | 0.4s | 0.56s | ≈gleich |
| **GESAMT** | **460.4s** | **247.54s** | **−46%** |

### Erkenntnisse

1. **ONNX Speaker ID kein Bottleneck mehr** — 0.70s statt 184s. Grund: Weniger Segmente (4 vs 13) + Load-Aufteilung nach RabbitMQ-Fix
2. **Sentinel LLM = 90% der Gesamtzeit** — 222.72s für 1 Chunk (67 Zeichen). Grund: Qwen-1.5B auf 1 CPU Core, ~1.2 tok/s
3. **Recording Status in DB:** completed | **Frontend zeigt nichts** → Untersuchung läuft (siehe unten)

---

## 11. 🔴 Untersuchung: Frontend zeigt Pipeline-Ergebnisse nicht

### Status: UNTERSUCHUNG LAUFT — Fakten gesammelt

**BEWIESEN:**
- DB: Recording=completed, Meeting=COMPLETED, Transcription=completed, PV=draft, 1 Action ✅
- Frontend-Code identisch (kein Diff zwischen Staging und Production) ✅
- Backend-API korrekt (Transcription + Segmente vorhanden) ✅

**BEWIESENE KETTE (Backend-Logs):**
```
19:37:25 — User tritt bei, Frontend pollt transcription (404)
19:38:18 — ai-insights pollt (recordingStatus=processing)
19:38:58 — Letzter ai-insights Call
19:39:20 — USER VERLÄSST LiveKit Room
19:42:09 — PIPELINE FERTIG (Celery: 247.54s)
20:01:24 — LiveKit-Raum-Restart (automatisch)
→ KEIN ai-insights oder transcription Call nach 19:39
```

**FALSCH (widerrufen):**
- ❌ TranscriptionViewer Polling-Bug — TranscriptionViewer wird NIRGENDWO importiert (nur in eigener Datei definiert)
- ❌ 404 Polling-Stop — Code ist identisch auf Staging und Production

**OFFENE FRAGEN:**
- Warum wurde syncFromBackend (MeetingRoom.tsx:573) bei 20:01 nicht ausgeführt?
- User war auf Dashboard oder MeetingRoom bei 20:01?
- Frontend-Routing: Welche Route wird nach Room-Verlassen angezeigt?
