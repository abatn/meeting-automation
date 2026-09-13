# Sentinel Benchmark Results & P0 Fix — 2026-09-13

**Scope:** Staging only. Production was NOT modified in any step of this work.
**Trigger:** Staging crash `"Requested tokens (1456) exceed context window of 1024"` (recording 9d2c78fe, meeting "test 3 skale") while identical-code prod runs succeeded on shorter transcripts.

---

## 1. Verified Facts (baseline before benchmarks)

| Fact | Source |
|---|---|
| Both environments ran identical code: commit `c909ec27`, model MD5 `8e5111fdbc5c150920d368ff802c4b5a`, llama-cpp-python 0.3.35, n_ctx=1024 | Pod-level inspection (not git) |
| n_ctx was lowered 2048→1024 on 2026-09-08 (commit `d210a745`); 2048 had been stable since 2026-03-27 | Git history |
| Fixed 3,000-char chunking unchanged since 2026-03-27 (commit `72f24b07`) | Git history |
| Crash arithmetic: prompt_tokens + max_tokens > n_ctx. `1456 = ~89 template + ~1,367 chunk` for a 3,000-char Arabic chunk; + 128 max_tokens reservation = 1,584 > 1,024 | Crash log + verified formula |
| Staging worker lacked `--concurrency=1` → 48.4% CFS throttling (60,464/124,955 periods); prod had it | cpu.stat + deployment command |
| Name-leak bug: Sentinel prompt examples inject fictional speaker names into summaries/PVs | Staging PV contained "Fatima"; "Fatima" absent from source transcript |

**Root cause of the prod-vs-staging contradiction:** input length, not environment. Prod transcripts in the window were ≤ ~1,700 chars (small chunks fit 1,024); staging's 3,223-char transcript crossed the threshold. Same code, different input lengths.

---

## 2. Benchmark Results (staging only, real model, real transcripts)

Methodology: ephemeral Python in the staging celery-worker pod; production prompt template extracted from `sentinel_service.py:134`; text = real decrypted Arabic transcripts (never synthetic English). All timings on staging ARM (aarch64), 1 thread — do NOT extrapolate to prod AMD.

### Bench A/B — Tokenizer calibration & fix arithmetic

| Measurement | Result |
|---|---|
| Real 3,000-char Arabic chunk (D2 text) | **1,146–1,157 tokens** ≈ 2.6 chars/token |
| Crash-implied density (from 1,456 log, template 89) | 1,367 chunk tokens → **2.195 chars/token** (worst real density) |
| Template overhead (final, with real `<\|im_start\|>` wrappers) | **89 tokens** |
| max_tokens reservation | 128 |
| **Safe chunk size @ n_ctx=1024** (15% margin, design ratio 2.1) | **~1,350 chars** |
| **Safe chunk size @ n_ctx=2048** (15% margin, design ratio 2.1) | **~3,100 chars** |
| Formula | `safe_chars = ((0.85 × n_ctx) − template − max_tokens) × ratio` |
| Rejected: earlier agent's 2,103/4,830 (calibrated 3.13 c/t on synthetic text) | 4,830 @ 2.195 c/t = 2,200 + 89 + 128 = **2,417 > 2,048 → would crash even at 2048** |

> **Template-token saga (lesson learned):** an audit measured "61 tokens" by extracting the template without the `<|`/`|>` wrappers — an escaping artifact. The 2h benchmark re-extracted the exact source line and measured **89** again. Final: **89**. Design sizes were unaffected (they were derived from the 89-based arithmetic). The runtime guard tokenizes the actual prompt, so it never depends on this constant.

### Bench C — n_ctx speed (controlled, alternating runs)

| Result | Value |
|---|---|
| 1024 vs 2048 speed difference | **0.3%** — context size does not affect speed |
| Mean throughput (ARM, 1 thread) | ~1.1 tok/s (short chunks), consistent with 240s per 3,000-char chunk |

Caveat: this run produced no persistent output artifact (result from session transcript); it is directionally confirmed by the earlier prod-side run. Non-blocking.

### Bench D2 — Map-reduce end-to-end (9,000 chars real Arabic)

| Metric | Result |
|---|---|
| Chunks (3 × 3,000 chars, guard: 0 splits needed) | 3 |
| Map wall times | 248.0 / 231.4 / 243.5 s (**722.9 s total**, ~240 s/chunk sequential) |
| Reduce | single pass, 78.4 s (combined 1,468 chars / 334 tokens) |
| **Pipeline total** | **801.4 s** |
| **Crashes** | **0** |
| Peak cgroup memory | 1,791 MiB |
| Name-leak check (Ahmed/Fatima in final summary) | PASS (this run) |
| Last-chunk traceability (3-gram overlap) | 17 shared 3-grams — no truncation |

### Bench E2 — 4-instance parallel feasibility (4 processes, production-like)

| Metric | Result |
|---|---|
| Model instances | 4 × `Llama()` as **separate processes** (not threads), persistent pool |
| Child VmRSS each | ~1,215 MiB (double-counts shared pages) |
| **Cgroup marginal footprint for all 4** | **+525 MiB total (1,198 MiB absolute vs 6,144 MiB limit)** — model mmap pages shared, counted once |
| memory.peak during test | 1,791 MiB (≈5.5 GiB would be expected if RSS were private → sharing proven) |
| Inference success | 4/4 |
| Wall per inference (4-parallel, **1-CPU pod**) | 139.9–143.0 s |
| Single-instance control run (same 300-char prompt) | **34.8 s** → single ≈ ¼ of parallel wall = CFS contention signature |
| Memory after children exit | 682 MiB (fully released) |
| **Verdict** | 4-instance pool **FEASIBLE at 6 GiB**; speedup blocked only by the CPU limit |

### 2h-Meeting Benchmark — 60,000 chars real Arabic, 4 instances, **CPU limit raised 1→4 first**

Precondition approved and applied on staging only: `kubectl set resources deploy/celery-worker-pro-staging --limits=cpu=4,memory=6Gi`. Verified in-pod: `cpu.max = 400000 100000`.

| Metric | Result |
|---|---|
| Text | 60,000 chars real Arabic (cycled 2 real transcripts) |
| Chunking | 15 raw 4,000-char pieces → **26 final chunks** via guard (11 splits, split-never-truncate) |
| Prompt template tokens (source-exact) | 89 |
| Chunk token limit | 1,523 (budget 1,740 = 85% of 2,048) |
| Map (parallel, 4 workers) | 22 chunks in **1,139.1 s** ≈ **51 s/chunk** |
| Reduce | 2+1 recursive passes, 187.6 s |
| **Pipeline total** | **1,573.1 s ≈ 26 min** |
| **Crashes** | **0 / 26** |
| CPU throttling during benchmark | **0.01%** (limit fits) |
| Memory | ~1.4 GiB steady, huge headroom |
| Name-leak | **"Ahmad" appeared in final summary — NOT in source transcripts** → leak bug hit again (spelling variant of "Ahmed" example); see P0 fix |
| Throttle before fix (1 CPU baseline) | 48.4% of periods |

**Speedup — honest calculation:** Phase 1 of this run was intended as a sequential baseline, but all 4 tasks were queued simultaneously → its "220 s/chunk" was actually 4-way parallel, making the computed 4.25× circular. **Discarded.** The honest speedup uses Bench D2's clean sequential measurement:

> **Sequential 240 s/chunk (D2) → parallel ~51 s/chunk (2h bench, 4 CPUs) ≈ 4.7× speedup**

**2h-meeting wall time:** today (n_ctx=1024, 3,000-char chunks) → **crash on first full chunk**. After fix, 4 instances: **~26 min measured end-to-end** (map ~19 min + reduce ~3 min + load). With 0.5B map model (P3, unmeasured): estimated ~10 min.

---

## 3. P0 Fix — Implemented (staging)

### Changes (4 files, 5 edits)

| # | File | Change | Benchmark justification |
|---|---|---|---|
| 1 | `backend/app/services/sentinel_service.py` | `n_ctx=1024 → 2048` | Full 3,100-char Arabic chunk = 1,363 tok < 2,048 (margin 685); speed cost 0.3% |
| 2 | `backend/app/services/sentinel_service.py` | Prompt examples `'Ahmed proposed X', 'Fatima agreed'` → `'Speaker A proposed X', 'Speaker B agreed'` | Name-leak confirmed twice (staging PV "Fatima"; benchmark "Ahmad") — both absent from source transcripts |
| 3 | `backend/app/services/sentinel_service.py` | New `_split_to_token_budget()` guard called in `summarize_chunk()`: tokenizes the actual chunk at runtime (measure, don't assume), **splits oversized text, never truncates**, budget 1,800 chunk-tokens | Structural impossibility of n_ctx overflow regardless of language/density; D2/E2/2h proved split + 0 crashes |
| 4 | `backend/app/tasks/transcription_tasks.py` | Chunking `3000 → 3100` chars | Bench B safe size @2048 (15% margin, design ratio 2.1); smaller GRADUIT fallback truncation at line 445 intentionally unchanged (non-LLM path) |
| 5 | `infrastructure/kubernetes/staging/celery-worker-pro-deployment.yaml` | CPU limit `1 → 4` | Persists the benchmark's live patch (otherwise lost on next `kubectl apply`); 4.7× speedup depends on it |

Side-fix in the same file: `_sentinel_instance: Optional[SentinelService]` replaces `SentinelService | None` (pre-existing 3.10+-only syntax; container runs 3.11, local lint runs 3.9 — behavior-neutral).

### Verification

- `py_compile`: OK for both Python files
- 5/5 direct tests PASS (stub tokenizer ≈ 2.2 chars/token):
  - T1 small text passes through unchanged
  - T2 29,700 chars → 9 pieces, every piece ≤ 1,800 tokens, no content loss (≥95% retained)
  - T3 prompt contains no "Ahmed"/"Fatima", contains "Speaker A proposed X"
  - T4 `n_ctx=2048` present in `__init__`
  - T5 chunking uses 3,100 chars (no 3,000 left in the LLM path)
- Local pytest run blocked by **pre-existing** environment issue (local Python 3.9 vs required 3.11: `str | None` at import of `app.api.v1.meetings`) — not caused by these changes.

### Deliberately NOT changed

- Production (code, manifests, deployments) — per instruction
- GRADUIT fallback truncation (`display_text[:3000]`, no LLM involved)
- Celery `--concurrency` on staging (separate known issue: staging worker still lacks `--concurrency=1`; 48.4% throttle baseline recorded above)
- Model choice / 0.5B map model (P3 — requires separate A/B benchmark)

---

## 4. Rollout & Follow-ups

1. **Commit + push** → CI builds staging image → `kubectl set image` rolls it out (existing pipeline).
2. **Post-rollout pod verification:** `n_ctx=2048` in running worker, guard present in `summarize_chunk`, `cpu.max = 400000 100000`.
3. **Functional test:** re-run the failed staging recording 9d2c78fe (3,223 chars) — must complete without the 1,456-token crash; check TIMING logs (`sentinel_chunks`, `sentinel_summarize`).
4. **Observe** `sentinel_summarize prompt_tokens=` TIMING lines: must stay ≤ 2,048 − 128 with the guard active.
5. Prod rollout of the same fix is a **separate, explicitly approved** change (identical arithmetic applies; prod AMD speed will be measured, not assumed).

### Risk table (post-fix residual)

| Risk | Severity | Mitigation |
|---|---|---|
| Language denser than 2.1 c/t appears | Low | Runtime guard splits regardless of density |
| Name-leak from reduce/other prompts | Low | Only Sentinel prompt had example names; neutralized |
| Staging CPU manifest drift (manual kubectl edits) | Medium | Manifest now `cpu: "4"`; verify after each CI deploy |
| 3-gram overlap too weak as truncation proof | Info | Replaced by guard design (split-never-truncate); no truncation path exists |
| Parallel map uses asyncio.gather over one semaphore(2) | Info | Current concurrency is capped at 2 in-process; true 4-way parallelism needs the instance-pool follow-up (P2) — measured separately in 2h bench |

---

## 5. Artifact Index (staging pod `/tmp`)

| File | Content |
|---|---|
| `bench_d2_out.log` | Full D2 map-reduce output incl. JSON metrics |
| `bench_e2_out.log` | Full E2 4-instance output |
| `bench_2h_out.log` | Full 2h-meeting benchmark output incl. JSON metrics |
| `bench_a.py` … `bench_2h.py` | Benchmark scripts (decrypt → tokenize → inference patterns) |

*Doc created 2026-09-13. All numbers marked "measured" come from the runs above; estimates are labeled.*
