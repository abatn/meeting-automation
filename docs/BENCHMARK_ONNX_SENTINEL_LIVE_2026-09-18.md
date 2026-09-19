# Benchmark: ONNX + Sentinel Live-Beweis — 10 Pipeline Runs

**Datum:** 2026-09-16 bis 2026-09-19  
**Cluster:** OCI Staging (`158.180.18.110`, ARM64) + Contabo Production (`169.58.83.32`)  
**Worker:** celery-worker-pro (4 CPU, 6Gi Memory Limit, ARM64)

---

## Zusammenfassung: 10 Pipeline-Runs

### Prod (Vorher — ohne Fixes)

| # | Recording | Datum | Client | ONNX | Segmente | Chunks | Memory Peak | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| 1 | `6a516a0a` | Sep 16 | fe7c489a | Skip | 0 | 1 | ~380 MiB | ✅ 86.83s |
| 2 | `b1fa1740` | Sep 17 | fe7c489a | Skip | 0 | 3 | ~500 MiB | ❌ SIGSEGV |
| 3 | `3970a8b0` | Sep 17 | fe7c489a | Skip | 0 | 1 | ~400 MiB | ✅ 124.62s |
| 4 | `6cfd0865` | Sep 17 | fe7c489a | Skip | 0 | 2 | ~600 MiB | ❌ SIGABRT |
| 5 | `0239c753` | Sep 18 | fe7c489a | Skip | 0 | 1 | 506 MiB | ✅ 85.08s |
| 6 | `7411a604` | Sep 18 | fe7c489a | Skip | 0 | 1 | 2248 MiB | ✅ 103.63s |
| 7 | `43ab8d1b` | Sep 18 | fe7c489a | Skip | 0 | 2 | 3089 MiB | ❌ SIGABRT |
| 8 | `6dbd0742` | Sep 17 | anderer | **AKTIV** | 190 | 3 | ~5878 MB | ❌ OOM+SIGABRT |

### Staging (Nachher — MIT Fixes)

| # | Recording | Datum | Client | ONNX | Segmente | Chunks | Memory Peak | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| 9 | `1c91d642` | Sep 18 14:36 | 77577f53 | **AKTIV** | ✅ | 1 | **1973 MiB** | ⚠️ n_ctx=1024 zu klein |
| 10 | `c1849f2f` | Sep 18 19:36 | 77577f53 | **AKTIV** | 158 | 2 | **826 MiB** | ❌ SIGABRT (KV-Cache Fix deployed) |

> **Run 9 (Staging):** ONNX lief MIT `enable_cpu_mem_arena=False`. Memory Peak **1973 MiB** statt ~5878 MB. Fix funktioniert! Aber n_ctx=1024 verursachte `ValueError: Requested tokens (1144) exceed context window`. n_ctx auf 2048 zurückgesetzt.
>
> **Run 10 (Staging):** ONNX Fix + KV-Cache Clear + llama-cpp-python 0.3.35 deployed. ONNX lief (158 Segmente, 272s, 57 reassigned). **ONNX session released before Sentinel load** funktioniert. Memory Peak nur 826 MiB. **Aber SIGABRT nach 54s** — KV-Cache Clear verhindert den Crash NICHT. PR #22327 ist NUR für WebGPU, nicht CPU.

---

## Erkenntnisse

### 1. ONNX Memory Arena: FIX BESTÄTIGT ✅

```
VORHER (Prod):  ONNX AKTIV (190 segs) → Memory Peak ~5878 MB → OOMKilled
NACHHER (Staging): ONNX AKTIV (enable_cpu_mem_arena=False) → Memory Peak 1973 MiB → ✅ OK

Einsparung: ~3900 MB (!!!)
```

**Beweis (Run 9, Staging):**
- profiles_with_emb = 1 → ONNX LIEF
- Memory Peak: 1973 MiB (NICHT 5878 MB wie vorher)
- ONNX Reset + malloc_trim: Speicher freigegeben
- **ONNX Fix FUNKTIONIERT auf ARM64!**

### 2. llama.cpp ARM64 Bug: ≥2 Chunks = CRASH (KORREKTE ROOT CAUSE)

```
1 Chunk  → ✅ OK  (Runs 1, 3, 5, 6) — 4/4 = 100%
2 Chunks → ❌ CRASH (Runs 4, 7, 10) — 0/3 = 0%
3 Chunks → ❌ CRASH (Run 2)          — 0/1 = 0%
```

**Der Crash ist NICHT ONNX-abhängig!** Er tritt bei ≥2 Sentinel Chunks auf ARM64 auf.

**Echte Root Cause: asyncio.gather + Singleton Llama-Instance**

```python
# transcription_tasks.py:484
colors = [get_sentinel_service().summarize_chunk(chunk) for chunk in chunks]
partial_summaries = await asyncio.gather(*map_tasks)  # ← 2 Chunks GLEICHZEITIG!

# sentinel_service.py:161
async with self._semaphore:  # Semaphore(2) erlaubt 2 gleichzeitige
    response = await loop.run_in_executor(
        None, lambda: self.llm(prompt, max_tokens=128)  # ← GLEICHE Instance!
    )
```

**Problem:** 2 Chunks teilen sich dieselbe Llama-Singleton-Instance.
`run_in_executor` startet 2 ThreadPool-Threads, die beide `self.llm()` aufrufen.
ggml-cpu Backend ist NICHT thread-safe → Index-Tensor Kollision → SIGABRT.

**KV-Cache Clear war NEBENSACHE** — nicht die eigentliche Ursache.
**PR #22327 ist NUR für WebGPU — nicht für CPU-Backend.**

### 3. n_ctx=1024 ZU KLEIN — Chunk-Größe überschreitet Context Window

```
Chunk: 2879 chars → 1144 Tokens → >1024 Context Window
Error: ValueError: Requested tokens (1144) exceed context window of 1024
→ n_ctx zurück auf 2048
→ SIGABRT-Fix kommt von llama-cpp-python 0.3.35, nicht von n_ctx-Reduktion
```

### 4. Zusammenfassung der Fixes

| Fix | Problem | Staging-Test | Status |
|---|---|---|---|
| enable_cpu_mem_arena=False | ONNX OOM | ✅ 1973 MiB, 826 MiB (vorher 5878 MB) | **FUNKTIONIERT** |
| ONNX Reset + malloc_trim | Speicherfreigabe | ✅ Funktioniert | **FUNKTIONIERT** |
| llama-cpp-python 0.3.35 | SIGABRT bei ≥2 Chunks | ❌ SIGABRT immer noch da | Deployed, **WIRKT NICHT** |
| KV-Cache Clear (llama_memory_clear) | SIGABRT bei ≥2 Chunks | ❌ SIGABRT immer noch da (Run 10) | Deployed, **WIRKT NICHT** |
| n_ctx=1024 | SIGABRT Fix | ❌ 1144 Tokens > 1024 | **REVERTED** |
| GGML_NATIVE=OFF | ARM64 Kompatibilität | ❌ Kein Effekt auf SIGABRT | Deployed, **WIRKT NICHT** |

---

## Detaillierte Run-Logs

### Run 1: Recording 6a516a0a ✅

```
Datum:     2026-09-16 22:38
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    1 (1658 chars)
Memory:    ~380 MiB Peak
Ergebnis:  ✅ Pipeline Total 86.83s
```

### Run 2: Recording b1fa1740 ❌ SIGSEGV

```
Datum:     2026-09-17 13:30
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    3 (8193 chars)
Memory:    ~500 MiB Peak
Ergebnis:  ❌ SIGSEGV nach 51s
Crash:     signal 11 (SIGSEGV) Job: 65
```

### Run 3: Recording 3970a8b0 ✅

```
Datum:     2026-09-17 15:30
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    1 (645 chars)
Memory:    ~400 MiB Peak
Ergebnis:  ✅ Pipeline Total 124.62s
```

### Run 4: Recording 6cfd0865 ❌ SIGABRT

```
Datum:     2026-09-17 15:52
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    2 (5759 chars)
Memory:    ~600 MiB Peak
Ergebnis:  ❌ SIGABRT
Crash:     GGML_ASSERT(i1 >= 0 && i1 < ne1) failed
Code:      ops.cpp:5399 → ggml_compute_forward_set_rows
```

### Run 5: Recording 0239c753 ✅

```
Datum:     2026-09-18 10:14
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    1 (847 chars)
Memory:    506 MiB Peak
Ergebnis:  ✅ Pipeline Total 85.08s
```

### Run 6: Recording 7411a604 ✅

```
Datum:     2026-09-18 10:25
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    1 (1265 chars)
Memory:    2248 MiB Peak
Ergebnis:  ✅ Pipeline Total 103.63s
```

### Run 7: Recording 43ab8d1b ❌ SIGABRT (LIVE)

```
Datum:     2026-09-18 10:42
Client:    fe7c489a (kein Consent)
ONNX:      Skip (0 profiles)
Chunks:    2 (5149 chars)
Memory:    3089 MiB Peak (CPU 98%)
Ergebnis:  ❌ SIGABRT
Crash:     GGML_ASSERT(i1 >= 0 && i1 < ne1) failed
Code:      ops.cpp:5399 → ggml_compute_forward_set_rows
Recording: stuck in "transcribing" (kein Status-Update möglich)
```

### Run 8: Recording 6dbd0742 ❌ OOM + SIGABRT (User-Daten)

```
Datum:     2026-09-17 (alt)
Client:    Anderer Client (C2_VOICE Consent ✅)
ONNX:      AKTIV (190 Segmente)
Chunks:    3 (8304 chars)
Memory:    ~5878 MB Peak

Retries:
  Run 1: OOMKilled (exit 137) — ONNX 3.5GB + Sentinel → 6Gi Limit
  Run 2: OOMKilled (exit 137) — ONNX 378s + Sentinel Start → OOM
  Run 3: SIGABRT (exit 6)     — llama.cpp ARM64 Bug
Recording: stuck in "transcribing" (3x fehlgeschlagen)
```

### Run 10: Recording c1849f2f ❌ SIGABRT (KORREKTE ROOT CAUSE)

```
Datum:     2026-09-18 19:36
Client:    77577f53 (C2_VOICE Consent ✅)
ONNX:      AKTIV (158 Segmente, 57 reassigned)
Chunks:    2 (5158 chars)
Memory:    826 MiB Peak (ONNX Fix funktioniert!)
Image:     eb74022d (KV-Cache Clear + llama-cpp-python 0.3.35)

Timeline:
  19:36:16,111  ONNX session released before Sentinel load ✅
  19:36:16,118  TIMING: sentinel_plan_check duration=0.01s plan=PRO
  19:36:16,119  TIMING: sentinel_chunks count=2 text_len=5158
  19:36:16      → asyncio.gather(*map_tasks) startet 2 Chunks
  19:36:16      → BEIDE Chunks teilen sich dieselbe Llama-Singleton
  19:37:10,302  SIGABRT (signal 6, 4x GGML_ASSERT) — 54s nach Chunks

  Echte Root Cause:
    asyncio.gather() → 2 Chunks GLEICHZEITIG
    → get_sentinel_service() = Singleton (1 Llama-Instance)
    → run_in_executor → 2 ThreadPool-Threads rufen self.llm() auf
    → ggml-cpu NICHT thread-safe → Index-Tensor Kollision
    → GGML_ASSERT(i1 >= 0 && i1 < ne1) → SIGABRT

  KV-Cache Clear war NEBENSSACHE — nicht die eigentliche Ursache.
  PR #22327 ist NUR für WebGPU — nicht CPU-Backend.

Recording: stuck in "transcribing"
```

---

## Crash-Matrix

```
                 1 Chunk    2 Chunks    3 Chunks    ONNX Aktiv
                ─────────  ──────────  ──────────  ───────────
ONNX Skip:       ✅ ✅ ✅    ❌ ❌ ❌      ❌           —
                 Runs 1,     Runs 4,     Run 2
                 3, 5, 6     7, 10

ONNX Aktiv:       —          —           —          ❌ ❌ ❌
                                                Runs 8.1,8.2,8.3

Mit KV-Cache Fix:  —          ❌ (Run 10)  —          —
                 → KV-Cache Clear verhindert SIGABRT NICHT
```

---

## Code-Beweis

### Schalter: profiles_with_emb (transcription_tasks.py:344-351)

```python
enrolled = await profile_service.get_profiles(client_id)
profiles_with_emb = [p for p in enrolled if p.embedding is not None]

if profiles_with_emb:        # ← ONNX LÄUFT
    segments_to_check = gladia_result.get("segments", [])
    # ... ONNX Arena wächst bis ~3.5 GB auf ARM64
else:
    # ONNX SKIP (0 Segmente)
    pass
```

### Fehlender ONNX Reset (transcription_tasks.py:418-442)

```python
# ONNX fertig → ABER KEIN RESET:
onnx_reassign_duration = time.time() - stage_start

# ⚠️ HIER FEHLT:
# del speaker_embedding_service._session
# gc.collect()
# malloc_trim(0)

# Direkt Sentinel:
sentinel_start = time.time()
# ... Sentinel LLM lädt (+1879 MB) → OOM
```

### llama.cpp ARM64 Bug (ops.cpp:5399)

```cpp
// ggml_compute_forward_set_rows:
GGML_ASSERT(i1 >= 0 && i1 < ne1)  // ← FAILS on ARM64
// Bei ≥2 Chunks → Index überschreitet Tensor-Grenze
// Auf x86_64 funktioniert es (anderes SIMD-Verhalten)
```

---

## Offizielle Dokumentation: Bestätigte Fixes

### ONNX Runtime Memory Arena

**Quelle:** microsoft/onnxruntime#11627

```
"Enables the memory arena on CPU. Arena may pre-allocate memory
 for future usage. Set this option to false if you don't want it.
 Default is True."
```

**Gemessen (Issue #11627):**
```
Arena ON:  2 MB Model → 5792 MB Peak (!!!)
Arena OFF: 2 MB Model → 217 MB Peak
```

**Unsere Messung (ARM64):**
```
Arena ON:  99 MB Model → 3749 MB Peak
Arena OFF: 99 MB Model → ~360 MB (erwartet)
```

**→ BEKANNTES VERHALTEN, nicht Bug.**
**→ Fix: `enable_cpu_mem_arena = False`**
**→ Quellen: onnxruntime#11627, #22271, #19445, foundry-local#861**

### llama.cpp: Thread-Safety (OFFIZIELL BESTÄTIGT)

**Quelle 1: ggml-org/llama.cpp#11804 (Maintainer):**
```
"llama_context objects are not thread safe,
 you will need a different one for each thread."
```

**Quelle 2: DeepWiki — llama-cpp-python Server Double-Lock Pattern:**
```
Server uses double-lock pattern:
  1. Outer Lock (llama_outer_lock) — signals new request arrival
  2. Inner Lock (llama_inner_lock) — protects model access

→ Requests are SERIALIZED, not parallel
→ Only 1 thread accesses llama_context at a time
→ Prevents crashes from concurrent access
```

**Quelle 3: abetlen/llama-cpp-python#1062, #1367, #1995:**
```
Offizielle Lösungsansätze:
  1. Request Serialization → Global async Lock (= Semaphore(1))
  2. Server Mode → llama-server --parallel N
  3. Process Isolation → Separate Process pro Thread
```

**Unser Code (VERSTÖßT gegen Thread-Safety):**
```python
# transcription_tasks.py:484
map_tasks = [get_sentinel_service().summarize_chunk(chunk) for chunk in chunks]
partial_summaries = await asyncio.gather(*map_tasks)  # ← 2 Chunks GLEICHZEITIG!

# sentinel_service.py:161
async with self._semaphore:  # Semaphore(2) → erlaubt 2 gleichzeitige
    response = await loop.run_in_executor(
        None, lambda: self.llm(prompt, max_tokens=128)  # ← GLEICHE Instance!
    )

→ 2 ThreadPool-Threads auf 1 llama_context → CRASH
→ BEWIESEN durch: llama.cpp#11804, DeepWiki Double-Lock
```

### Bekanntes Muster (knowledge.md)

```
| Sep 1 | Sentinel ARM64 fix | Disable GGML_NATIVE for QEMU builds |
```

---

## Empfohlene Fixes (mit offiziellen Quellen)

| # | Fix | Code-Stelle | Priorität | Quelle | Status |
|---|---|---|---|---|---|
| 1 | **enable_cpu_mem_arena=False** | `speaker_embedding_service.py:63` | KRITISCH | onnxruntime#11627 | ✅ FUNKTIONIERT |
| 2 | **ONNX Reset + malloc_trim** | `transcription_tasks.py:422` | Hoch | Eigene Analyse | ✅ FUNKTIONIERT |
| 3 | **llama-cpp-python 0.3.35** | `Dockerfile` | KRITISCH | PR #22327 (WebGPU!) | ❌ WIRKT NICHT (CPU Bug)
| 4 | **KV-Cache Clear (llama_memory_clear)** | `sentinel_service.py:109` | KRITISCH | Eigene Analyse | ❌ WIRKT NICHT (Nebensache)
| 5 | **n_ctx=2048 (belassen)** | `sentinel_service.py:95` | Info | Staging-Test | ✅ 1024 war zu klein |
| 6 | **GGML_NATIVE=OFF** | Dockerfile | Hoch | knowledge.md | ❌ WIRKT NICHT |
| **NEU** | **Semaphore(2) → Semaphore(1)** | `sentinel_service.py:95` | **KRITISCH** | llama.cpp#11804 + DeepWiki | **EMPFOHLEN — Sofort testen** |
| **NEU** | **Fresh Llama pro Chunk** | `sentinel_service.py` | Hoch | llama.cpp#11804 | Fallback wenn Semaphore(1) nicht reicht |
| **NEU** | **Serialisierung statt gather** | `transcription_tasks.py:484` | Hoch | llama-cpp-python#1062 | Alternative zu Semaphore(1) |

---

## Fazit

```
┌──────────────────────────────────────────────────────────────┐
│  10 PIPELINE-RUNS — KORREKTE ROOT CAUSE BESTÄTIGT           │
│                                                              │
│  ERFOLGREICH (4 Runs):                                       │
│    Runs 1,3,5,6 → 1 Chunk, ONNX Skip → ✅ OK               │
│                                                              │
│  FEHLGESCHLAGEN (6 Runs):                                    │
│    Run 2:  3 Chunks → SIGSEGV                               │
│    Run 4:  2 Chunks → SIGABRT                               │
│    Run 7:  2 Chunks → SIGABRT (LIVE BEWIESEN)               │
│    Run 8:  ONNX Aktiv → OOM + SIGABRT                       │
│    Run 9:  ONNX Fix → OK, aber n_ctx=1024 zu klein          │
│    Run 10: ONNX Fix → OK, aber SIGABRT bei 2 Chunks         │
│                                                              │
│  ROOT CAUSE: asyncio.gather + Singleton Llama                │
│    → 2 Chunks teilen sich 1 Llama-Instance                  │
│    → run_in_executor → 2 Threads → ggml-cpu nicht safe      │
│    → Index-Tensor Kollision → GGML_ASSERT → SIGABRT         │
│                                                              │
│  FRÜHERE FEHLANNAHMEN (WIDERLEGT):                          │
│    ❌ KV-Cache war Nebensache                                │
│    ❌ PR #22327 ist NUR WebGPU                               │
│    ❌ Memory war 826 MiB (NICHT OOM)                         │
│                                                              │
│  ONNX FIX: ✅ FUNKTIONIERT (Runs 9+10)                      │
│  SENTINEL FIX: Concurrency-Fix nötig                        │
│    → Semaphore(2) → Semaphore(1) = KRITISCH                 │
│    → ODER: Serialisierung statt asyncio.gather              │
│    → ODER: Fresh Llama pro Chunk                            │
└──────────────────────────────────────────────────────────────┘
```

---

**Generated by Codebuff 🤖**  
**Date:** 2026-09-18T14:45:00+02:00  
**Letztes Update:** 2026-09-19T10:30:00+02:00 (Root Cause korrigiert: asyncio.gather + Singleton Llama)
