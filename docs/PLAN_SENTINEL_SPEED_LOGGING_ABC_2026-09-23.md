# Plan A/B/C — Sentinel Speed + Logging + Rollback

**Datum:** 2026-09-23  
**Status:** freigegeben durch User („notiere … und setze ein")  
**Scope:** Staging first; Production nur mit separater Freigabe  
**HEAD zum Planzeitpunkt:** `61b3e290`  
**Regeln:** kein `rm`, kein `docker prune`, kein `deploy-production`, keine erfundenen Optionen — nur offizielle llama.cpp / llama-cpp-python / Celery-Parameter

---

## Kontext (3 Zeilen)

1. Run1/Run2: Overhead sitzt in `sentinel_llm` (6.3s / 136.4s) — In-Pod: tok/s 1.4–4.1, `n_threads=2`, `n_batch=512` Defaults.  
2. Service-TIMING (`sentinel_summarize` etc.) fehlt in Worker-Logs, weil Celery `sys.stdout` als `LoggingProxy` setzt und `setup_logging()` dorthin bindet (Recursion-Drop) — Task-Logger sieht man trotzdem.  
3. Ziel: **A** = offizielle Speed-Parameter in-Pod messen, **B** = Logging an echte Streams + Celery-Init, **C** = A+B.

---

## Plan A — Staging Speed-Mess-Grid (in-Pod, kein Commit)

**Ziel:** offizielle `Llama()`-Parameter auf ARM64 (4 CPU) gegen Baseline messen.  
**Wo:** `celery-worker-pro-staging` Pod, Skript nur nach `/tmp` — **kein** Repo-Commit, **kein** Deploy.

### Baseline (Ist)
| Parameter | Wert |
|-----------|------|
| `n_ctx` | 2048 |
| `n_threads` | 2 |
| `n_batch` / `n_ubatch` | 512 / 512 (Defaults) |
| `n_threads_batch` | None |
| `flash_attn` | False |
| `logits_all` | False |
| `max_tokens` (summarize) | 128 |
| Modell | `qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| gemessen (In-Pod) | cold_start 0.40s; chunk0 ~1.4 tok/s; chunk1 ~4.1 tok/s; gather Run2 136s |

### Mess-Grid (einzelne Läufe, gleiche Chunks, nacheinander)

| # | Variation | Offizielle Quelle / Hinweis |
|---|-----------|----------------------------|
| A1 | `n_threads ∈ {2, 4}` bei fix `n_batch=512` | llama.cpp: Threads = physische Kerne; 4 CPUs |
| A2 | `n_batch ∈ {512, 1024, 2048}` bei `n_threads=4` | llama-cpp-python Default 512; größere Batch → weniger Overhead |
| A3 | `n_threads_batch = n_threads` (bzw. 4) | Official: getrennte Compute-/Prompt-Threads |
| A4 | `logits_all=False` (Default, bestätigen) und **nicht** True (mehr RAM) | Default; True nur wenn nötig |
| A5 | `flash_attn=False` (Default auf CPU) | Auf CPU ohne GPU-Layer i.d.R. kein Gewinn — nur protokollieren |
| A6 | `max_tokens` nur beobachten (128 ist Produktionslimit) | Nicht erhöhen ohne separate Freigabe (n_ctx-Fenster) |

### Nicht anfassen (verboten / gemessen schlecht)
- `n_ctx` ↓ (Revert `d55bd062`)
- `Semaphore > 1` (ARM64 SIGABRT `4b7c8b99`)
- KV-Cache-Clear entfernen (`eb74022d`)
- `n_gpu_layers > 0` ohne GPU
- Modellwechsel 0.5B nur „unmeasured estimate" — separat freigeben

### Durchführung
1. Skript ` /tmp/measure_grid_abc.py` (oder erweitertes `measure_sentinel.py`) ins Pod.  
2. Pro Konfiguration: gleicher Text-Chunk (3100c + 1048c), `llm(prompt, max_tokens=128)`, `tok_per_sec` + Wall.  
3. Ergebnisse → Tabelle unten / Follow-up MD.  
4. Bestes Profil vorschlagen → erst **nach** OK in Code (`sentinel_service.py:102-107`) übernehmen.

### Akzeptanz
- Jede Reihe: `tok_per_sec`, `llm_dur`, Peak-CPU im Pod notiert.  
- Kein SIGABRT, kein OOM.  
- Empfehlung klar: „übernimmt A-x" oder „Baseline reicht".

### Rollback A
- Kein Code-/Image-Change → Rollback = **nichts tun**.  
- Temp-Skripte in Pod `/tmp` löschen (nur `/tmp`, kein `rm` im Repo).  
- Bei CPU/OOM während Messung: Messung abbrechen, Pod unverändert (läuft weiter).

---

## Plan B — Logging-Fix (Root-Service-TIMING sichtbar)

**Ziel:** `sentinel_service`-TIMINGs (`cold_start`, `sentinel_summarize`, `tok_per_sec`, …) in `kubectl logs` des Celery-Workers.

### Root-Cause (bewiesen)
1. Celery `worker_hijack_root_logger=True` → Root-Handler auf echtem stderr.  
2. Celery `worker_redirect_stdouts=True` → `sys.stdout = LoggingProxy(celery.redirected)`.  
3. Task importiert `app.main` → `setup_logging()` → `StreamHandler(sys.stdout)` = **Proxy**.  
4. Root-`logger.info` → Proxy-Recurse-Guard → **Record drop**.  
5. `get_task_logger` → `celery.task` mit eigenem stderr-Handler → sichtbar (Task-TIMING).  
6. Extra: `TextFormatter.format` nutzt `recordasctime` (NameError) — `logging_config.py:48`.

### Änderungen (Repo)

**B1 — `backend/app/core/logging_config.py`**
- Handler an **`sys.__stdout__`** bzw. **`sys.__stderr__`** binden (echte Streams, nicht Proxy).  
- Fallback: falls `__stderr__` fehlt → `sys.stderr`.  
- `TextFormatter`: `recordasctime` → korrekt via `self.formatTime(record)` / `record.asctime` nach `Formatter.formatTime`.  
- Optional: `json_format` unverändert (Default true).

**B2 — Celery-Worker-Init (bevorzugt soft)**  
Optionen (Reihenfolge nach Eingriff):
1. **Ohne Deploy-Change:** B1 allein reicht oft, weil Setup an `__stdout__` den Proxy umgeht.  
2. Falls nötig: Worker-Env / Startflag  
   - `worker_redirect_stdouts=False` (nur Worker-Command/YAML), **oder**  
   - `setup_logging()` explizit nach Celery-Logging-Init (z.B. in `celery_app.py` bei Import — Vorsicht: Reihenfolge vs. `already_setup`).  
3. **Nicht** empfohlen: `worker_hijack_root_logger=False` global, ohne Alternative — bricht Celery-eigene Logs.

**B3 — `sentinel_service.py`**  
- `logger = logging.getLogger()` (Root) **bleibt**, wenn B1 greift.  
- Alternativ (robuster gegen zukünftige Celery-Aenderungen): `get_task_logger(__name__)` analog `transcription_tasks` — **nur** wenn B1+Worker-Init nicht ausreichen. Nicht beides blind mischen.

### Akzeptanz
- Nach Deploy Staging: Worker-Logs enthalten JSON/Text mit `"logger":"root"` **und** `TIMING: sentinel_summarize` / `sentinel_cold_start`.  
- Kein Regression: Task-TIMING (`sentinel_gather`, `pipeline_total`) weiterhin da.  
- Backend/uvicorn: JSON-Logs weiterhin (Probe).

### Rollback B
1. **Code:** `git revert` des Logging-Commits (oder Checkout der vorigen `logging_config.py` + `sentinel_service.py`), Commit, Staging-Deploy.  
2. **Nur Worker-YAML** (falls B2.2 genutzt): alten `command`/Env-Wert restores — `infrastructure/kubernetes/staging/celery-worker*-deployment.yaml`.  
3. **Deploy-Rollback:** letztes gutes Backend-Image setzen (`kubectl set image` auf `61b3e290…` oder vorheriges Tag), `rollout status`.  
4. **Verifikation nach Rollback:** Task-TIMING sichtbar; Service-TIMING darf wieder fehlen (akzeptabel).  
5. **Nicht** per „Log löschen“ behandeln (Regel: *Löschen ist verboten*).

---

## Plan C — A + B (empfohlen, freigegeben)

| Reihenfolge | Schritt | Commit? |
|-------------|---------|---------|
| C1 | **Plan A** Speed-Grid in-Pod auf Staging messen | nein |
| C2 | Ergebnisse in MD/`BENCHMARK_*` nachtragen | ja (nur Docs) |
| C3 | **Plan B1** Logging-Fix (`logging_config.py`) | ja |
| C4 | Optional B2 nur wenn B1 in Worker reicht | YAML/Commit separat |
| C5 | Staging-Deploy + Akzeptanz (TIMING sichtbar) | CI Staging |
| C6 | Bestes A-Profil vorschlagen → Separate Freigabe für `n_threads`/`n_batch` im Code | erst nach OK |

### Reihenfolge-Regel
Erst **A messen**, dann **B fixen**, dann **gemeinsam verifizieren** — nicht umgekehrt, damit TIMING-Overhead (A) ohne Logging-Rauschen gelesen wird.

### Rollback C
- A: wie Rollback A (nichts).  
- B: wie Rollback B.  
- Falls beides deployed und kaputt: **zuerst B rollen** (Logging), A war nur Messung.  
- Full stop: Image auf `61b3e290` (Known-Good), Worker-Rollout, Logs prüfen.

---

## Offene Punkte außerhalb A/B/C (nicht in Scope, nicht löschen)

- WAL ~46G / Barman — Freigabe offen  
- Prod-TIMING erst nach Deploy-Freigabe (`deploy-production` nie auto)  
- `grafana-external`, NS `monitoring-staging`  
- `logging_config.py:48` wird in B1 mitbehandelt  

---

## Umsetzungsstand (2026-09-23)

- [x] MD mit A, B, C + Rollback geschrieben  
- [x] **B1** `logging_config.py`: Handler an `__stdout__`/`__stderr__`, TextFormatter `formatTime`  
- [x] B1 lokaler Smoke: `_real_stream`, TextFormatter, `setup_logging` OK (Python 3.11, py_compile + Snippet OK; `black` 24.1.1 + `isort` 5.13.2 via `.venv311` lief auf `logging_config.py`)  
- [x] A-Mess-Grid `/tmp/measure_grid_abc.py` in Staging-Pod  
- [ ] Staging-Deploy + Verify: `TIMING: sentinel_summarize` in Worker-Logs  
- [ ] Bestes A-Profil → separate Freigabe für `n_threads`/`n_batch` im Code  

**Rollback B1:** `git checkout -- backend/app/core/logging_config.py` + Staging-Deploy — siehe Rollback B oben.

---

## Plan A Ergebnisse 2026-09-23

**Pod:** `celery-worker-pro-staging-849bbdd5c-fzxhl` (container `celery-worker`), Modell `qwen2.5-1.5b-instruct-q4_k_m.gguf`, `n_ctx=2048`, `max_tokens=128`, gleiche Chunks (3100c + 1048c).

| CONFIG | COLD | W0 | TPS0 | W1 | TPS1 |
|--------|------|-----|------|------|------|
| baseline_t2_b512 | 0.42 | 61.13 | 0.69 | 22.35 | 1.48 |
| t4_b512 | 0.38 | 64.65 | 0.65 | 24.80 | 1.33 |
| t4_b1024 | 0.44 | 57.36 | 0.73 | 23.44 | 1.41 |
| t4_b2048 | 0.38 | 56.92 | 0.74 | 20.91 | 1.58 |
| t4_b1024_tb4 | 0.38 | 59.79 | 0.70 | 21.36 | 1.55 |
| t4_b1024_fa0_la0 | 0.40 | 58.13 | 0.72 | 23.42 | 1.41 |

(TPS = tok/s auf dem jeweiligen Chunk; COLD = Modell-Load-Sekunden; W = Wall-Sekunden.)

**Empfehlung:** Baseline reicht — `n_threads=4` bringt keinen konsistenten Gewinn (TPS0 0.65–0.74 vs. 0.69, TPS1 teils schlechter), größere `n_batch`/`n_threads_batch`/`flash_attn=False` liegen im Rauschen. Kein offizielles Profil ist klar besser; Übernahme in `sentinel_service.py:102-107` nicht nötig (separate Freigabe entfällt bzw. „Baseline beibehalten").

**Fehler:** keine — kein SIGABRT, kein OOM, kein Timeout; alle 6 Configs `MEASURE_GRID_DONE`.
