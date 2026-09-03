# TIMING Logs — Referenz & Extraktion

**Erstellt:** 2026-09-03
**Status:** ✅ Implementiert (commit e6e19af9)
**Code:** `backend/app/tasks/transcription_tasks.py`, `backend/app/services/sentinel_service.py`

---

## 1. Überblick

17 TIMING-Logs decken alle Pipeline-Stages ab. Damit lassen sich Bottlenecks ohne Prometheus identifizieren.

### Prod-Umgebung verifiziert

| Komponente | Status | Details |
|------------|--------|---------|
| llama-cpp-python | ✅ v0.3.35 installiert | `pip show llama-cpp-python` |
| Qwen-1.5B Modell | ✅ 1.1GB vorhanden | `/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| ONNX ECAPA-TDNN | ✅ 79.6MB | `/app/models/speaker_embeddings/ecapa-speaker-v1.onnx` |

---

## 2. Alle TIMING-Logs

### Pipeline-Hauptstages (transcription_tasks.py)

| # | Log-Zeile | Stage | Erwartete Dauer |
|---|-----------|-------|-----------------|
| 1 | `TIMING: s3_download duration=Xs` | S3 Download (MinIO) | <1s |
| 2 | `TIMING: gladia_transcription duration=Xs` | Gladia V2 Transkription | 5-15s |
| 3 | `TIMING: speaker_identification duration=Xs speakers=N` | Speaker ID (gesamt) | 1-200s |
| 4 | `TIMING: onnx_segment_reassignment duration=Xs segments=N reassigned=N` | ONNX Neuzuweisung | 1-30s |
| 5 | `TIMING: sentinel_plan_check duration=Xs plan=PRO` | Plan-Erkennung | <0.1s |
| 6 | `TIMING: sentinel_chunks count=N text_len=N` | Chunking | <0.1s |
| 7 | `TIMING: sentinel_gather duration=Xs chunks=N summaries=N` | Sentinel Gather (gesamt) | 10-250s |
| 8 | `TIMING: sentinel_llm duration=Xs` | Sentinel LLM (gesamt) | 10-250s |
| 9 | `TIMING: mistral_pv duration=Xs` | Mistral PV Generierung | 3-15s |
| 10 | `TIMING: persistence duration=Xs` | DB-Speicherung | <1s |
| 11 | `TIMING: pipeline_total duration=Xs` | Pipeline Gesamt | variabel |

### Speaker ID Sub-Steps (transcription_tasks.py)

| # | Log-Zeile | Stage |
|---|-----------|-------|
| 12 | `TIMING: speaker_id_profile_load duration=Xs profiles=N with_embeddings=N candidates=[...]` | DB-Profilabfrage |
| 13 | `TIMING: speaker_id_process_speakers duration=Xs speakers=N` | Speaker-Verarbeitung (gesamt) |
| 14 | `TIMING: speaker_id_exclusivity duration=Xs assigned=N` | Exklusiv-Zuweisung |
| 15 | `TIMING: speaker_id_enrollment duration=Xs enrolled=N consent=yes/no` | Auto-Enrollment |

### Sentinel Sub-Steps (sentinel_service.py)

| # | Log-Zeile | Stage |
|---|-----------|-------|
| 16 | `TIMING: sentinel_cold_start duration=Xs model=...` | Qwen-1.5B Kaltstart |
| 17 | `TIMING: sentinel_summarize prompt_tokens=X output_tokens=Y llm_dur=Xs tok_per_sec=Z` | Per-Chunk Inferenz |

---

## 3. TIMING-Logs extrahieren

### Production (169.58.83.32)

```bash
# Alle TIMING-Logs (letzte 500 Zeilen)
ssh root@169.58.83.32 "kubectl logs -n meeting-automation -l app=celery-worker-pro --tail=500 | grep TIMING"

# Live mitverfolgen
ssh root@169.58.83.32 "kubectl logs -f -n meeting-automation -l app=celery-worker-pro | grep TIMING"

# Nur Sentinel-Logs
ssh root@169.58.83.32 "kubectl logs -n meeting-automation -l app=celery-worker-pro --tail=1000 | grep 'TIMING: sentinel'"

# Nur Speaker-ID-Logs
ssh root@169.58.83.32 "kubectl logs -n meeting-automation -l app=celery-worker-pro --tail=1000 | grep 'TIMING: speaker'"

# Letzten Pipeline-Run extrahieren
ssh root@169.58.83.32 "kubectl logs -n meeting-automation -l app=celery-worker-pro --tail=2000 | grep TIMING | tail -20"
```

### Staging (158.180.18.110)

```bash
# Alle TIMING-Logs
ssh root@158.180.18.110 "kubectl logs -n meeting-automation-staging -l app=celery-worker-pro-staging --tail=500 | grep TIMING"

# Live mitverfolgen
ssh root@158.180.18.110 "kubectl logs -f -n meeting-automation-staging -l app=celery-worker-pro-staging | grep TIMING"
```

---

## 4. Erwartete Ausgabe (Beispiel)

```
TIMING: s3_download duration=0.18s
TIMING: gladia_transcription duration=11.94s
TIMING: speaker_id_profile_load duration=0.05s profiles=3 with_embeddings=2 candidates=['Abdelkader Batnini', 'Speaker 1']
TIMING: speaker_id_process_speakers duration=0.62s speakers=2
TIMING: speaker_id_exclusivity duration=0.01s assigned=2
TIMING: speaker_id_enrollment duration=0.30s enrolled=1 consent=yes
TIMING: speaker_id_total duration=0.70s speakers=2 resolved=2
TIMING: onnx_segment_reassignment duration=2.10s segments=4 reassigned=0
TIMING: sentinel_plan_check duration=0.03s plan=PRO
TIMING: sentinel_chunks count=1 text_len=785
TIMING: sentinel_cold_start duration=3.02s model=qwen2.5-1.5b-instruct-q4_k_m
TIMING: sentinel_summarize prompt_tokens=200 output_tokens=256 llm_dur=222.72s tok_per_sec=1.15
TIMING: sentinel_gather duration=222.72s chunks=1 summaries=1
TIMING: sentinel_llm duration=222.75s
TIMING: mistral_pv duration=3.92s
TIMING: persistence duration=0.56s
TIMING: pipeline_total duration=247.54s
```

---

## 5. Bekannte Messwerte (Production)

| Test | Datum | Gesamt | S3 | Gladia | Speaker ID | Sentinel | Mistral | Persist |
|------|-------|--------|-----|--------|------------|----------|---------|---------|
| 7cc15aba | 2026-08-22 | 460.4s | 0.1s | 6.6s | 184.2s | 252.8s | 11.2s | 0.4s |
| c93154af | 2026-08-23 | 247.5s | 0.2s | 11.9s | 0.7s | 222.7s | 3.9s | 0.6s |
| test smoke | 2026-09-03 | 205.8s | — | — | — | ~113s | — | — |

### Erkenntnisse

1. **Sentinel LLM = 90% der Gesamtzeit** — Qwen-1.5B auf 1 CPU Core, ~1.2 tok/s
2. **Speaker ID variabel** — 0.7s (2 Sprecher) bis 184s (13 Segmente, ONNX Thread-Thrashing)
3. **S3 + Gladia + Mistral + Persist = ~15s** — kein Bottleneck

---

## 6. Prometheus METRICS (parallel)

Die TIMING-Logs ergänzen die Prometheus-Metriken:

```python
PIPELINE_STAGE_DURATION.labels(stage="s3_download").observe(s3_duration)
PIPELINE_STAGE_DURATION.labels(stage="gladia_transcription").observe(gladia_duration)
PIPELINE_STAGE_DURATION.labels(stage="speaker_identification").observe(speaker_duration)
PIPELINE_STAGE_DURATION.labels(stage="sentinel_llm").observe(sentinel_duration)
PIPELINE_STAGE_DURATION.labels(stage="mistral_pv").observe(mistral_duration)
```

**Unterschied:**
- TIMING-Logs → `kubectl logs | grep TIMING` (sofort, kein Prometheus nötig)
- Prometheus → `/metrics` oder Grafana (historisch, Alerts möglich)

---

## 7. Pipeline-Struktur mit TIMING-Insertionspunkten

```
_process_recording_pipeline
│
├── s3_download ─────────────────────── TIMING: s3_download
│
├── gladia_transcribe ───────────────── TIMING: gladia_transcription
│
├── _identify_speakers ──────────────── TIMING: speaker_identification
│   ├── profile_load ────────────────── TIMING: speaker_id_profile_load
│   ├── process_speakers ────────────── TIMING: speaker_id_process_speakers
│   ├── exclusivity ─────────────────── TIMING: speaker_id_exclusivity
│   └── enrollment ──────────────────── TIMING: speaker_id_enrollment
│
├── onnx_reassign ───────────────────── TIMING: onnx_segment_reassignment
│
├── sentinel_plan_check ─────────────── TIMING: sentinel_plan_check
├── sentinel_chunks ─────────────────── TIMING: sentinel_chunks
├── sentinel_cold_start ─────────────── TIMING: sentinel_cold_start  (sentinel_service.py)
├── sentinel_summarize ──────────────── TIMING: sentinel_summarize   (sentinel_service.py)
├── sentinel_gather ─────────────────── TIMING: sentinel_gather
├── sentinel_llm ────────────────────── TIMING: sentinel_llm
│
├── mistral_pv ──────────────────────── TIMING: mistral_pv
│
├── persistence ─────────────────────── TIMING: persistence
│
└── pipeline_total ──────────────────── TIMING: pipeline_total
```

---

## 8. Commit-Referenz

| Commit | Datum | Änderung |
|--------|-------|----------|
| e6e19af9 | 2026-09-03 | feat(pipeline): add TIMING log statements for all pipeline stages |
| d52b1c14 | 2026-08-22 | Speaker ID Sub-Step TIMING (earlier attempt, docs only) |
| 14738738 | 2026-08-22 | Sentinel Sub-Step TIMING (earlier attempt, docs only) |
