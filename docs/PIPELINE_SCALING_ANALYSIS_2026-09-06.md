# Pipeline Scaling Analysis — 2026-09-06

## Was ist proportional zur Aufnahme?

| Stage | Proportional? | Skalierung | Code-Beleg |
|-------|---------------|------------|------------|
| **S3 download** | ✅ Ja | Linear zu Dateigröße | `file_size=2948166 bytes` (3 Min) |
| **Gladia transcription** | ✅ Ja | Linear zu Audio-Dauer | Externes API |
| **ONNX Speaker ID** | ✅ Ja | Pro Segment | `for seg in segments_to_check:` (line 263) |
| **Sentinel LLM** | ✅ Ja | Pro 3000 Zeichen | `chunks = [display_text[i:i+3000]]` (line 356) |
| **Mistral PV** | ✅ Ja | Linear zu Text-Länge | `full_transcript=display_text` (line 370) |
| **Persistence** | ❌ Nein | Konstant | DB-Write |

## Feste Kosten (nicht proportional)

| Kosten | Wert |
|--------|------|
| ONNX Model-Load | ~3-5s (Cold Start) |
| Sentinel Model-Load | ~2-3s (Cold Start) |

## Extrapolation basierend auf Code-Logik

### 3-Minuten Recording (aktuell)
```
text_len = 1963 chars → 1 chunk → 1× Sentinel Call
segments = ~5-10 → 5-10× ONNX Embeddings
Pipeline Total: ~494s (mit Retry ~580s)
```

### 10-Minuten Recording (Hypothese basierend auf Code)
```
text_len = ~6500 chars → 2-3 chunks → 2-3× Sentinel Calls (parallel)
segments = ~15-30 → 15-30× ONNX Embeddings
Pipeline Total: ~650-800s (extrapolated)
```

### 20-Minuten Recording
```
text_len = ~13000 chars → 4-5 chunks → 4-5× Sentinel Calls (parallel)
segments = ~30-60 → 30-60× ONNX Embeddings
Pipeline Total: ~900-1200s
```

## ⚠️ Entscheidender Faktor: ONNX ist NICHT parallelisiert

```python
# Line 263: SEQUENTIAL loop — NOT parallel
for seg in segments_to_check:
    seg_embedding = await speaker_embedding_service.extract_embedding(seg_audio)
```

**ONNX verarbeitet jedes Segment SEQUENTIELL.** Das ist der Hauptbottleneck:
- 3 Min → ~5-10 Segmente → 260s (52s pro Segment)
- 10 Min → ~15-30 Segmente → **~800-1500s** (exponentiell langsamer wegen CPU-Throttling)

## Sentinel: Parallel, aber auf CPU

```python
# Line 358: PARALLEL via asyncio.gather
map_tasks = [get_sentinel_service().summarize_chunk(chunk) for chunk in chunks]
partial_summaries = await asyncio.gather(*map_tasks)
```

Sentinel chunks werden parallel verarbeitet, aber auf **einem CPU-Core** (AMD64, 1 Core Limit). Die Parallelisierung bringt wenig auf CPU.

## Fazit

| Recording-Länge | Erwartete Pipeline Time | ONNX-Anteil |
|-----------------|------------------------|-------------|
| 3 Minuten | ~494s (580s mit Retry) | 260s (53%) |
| 10 Minuten | ~650-800s | ~500s (63%) |
| 20 Minuten | ~900-1200s | ~800s (67%) |

**ONNX wird zum dominanten Bottleneck bei längeren Aufnahmen.**

## Empfehlung

1. **10-Minuten-Test** durchführen zur Verifikation
2. **ONNX parallelisieren** (asyncio.gather für Embeddings)
3. **ONNX überspringen** wenn 0 Profile existieren (spart 260s)
4. **Soft Time Limit** von 540s auf 900s erhöhen (für 10+ Minuten Aufnahmen)

## Production TIMING Logs (06.09.2026)

### test smoke 2 (3 Min Recording)
| Stage | Run 1 | Run 2 (retry) |
|-------|-------|---------------|
| s3_download | 0.20s | 0.11s |
| gladia_transcription | 12.81s | 12.62s |
| speaker_id_process_speakers | 303.85s | 260.27s |
| sentinel_llm | 212.48s | 207.24s |
| mistral_pv | ❌ killed | 10.46s |
| persistence | ❌ killed | 0.46s |
| **pipeline_total** | ❌ 540s killed | **493.71s** |

### test smoke 4 (4 Min Recording)
| Stage | Run 1 | Run 2 (retry) |
|-------|-------|---------------|
| s3_download | 0.12s | 0.39s |
| gladia_transcription | 14.01s | 8.07s |
| speaker_id_process_speakers | 264.79s | — |
| sentinel_llm | 260.10s | — |
| mistral_pv | ❌ killed | 18.32s |
| persistence | ❌ killed | 13.80s |
| **pipeline_total** | ❌ 540s killed | **581.38s** |

### Bottleneck Breakdown (Production AMD64 vs Staging ARM64)
| Stage | Prod (AMD64) | Staging (ARM64) | Ratio |
|-------|-------------|-----------------|-------|
| ONNX Speaker ID | 260-304s | ~27s | **10x slower** |
| Sentinel LLM | 207-260s | ~56s | **4x slower** |
| Gladia | 12-14s | ~12s | same |
| Mistral PV | 10-18s | ~5s | 2-3x slower |
| **Total** | **494-581s** | ~113s | **4-5x slower** |

### Soft Time Limit History
| Commit | Date | soft_time_limit | Context |
|--------|------|-----------------|---------|
| `c35107ee` | 2026-06-13 | **540s added** | "Celery config hardening" |
| All commits 28.07–05.08 | — | 540s unchanged | No modification |
| Current HEAD | 2026-09-06 | 540s | Same as day one |

**The 540s soft time limit has been in production since June 13, 2026 — never changed.**
