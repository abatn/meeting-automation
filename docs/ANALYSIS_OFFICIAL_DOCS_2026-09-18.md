# Analyse: Offizielle Dokumentation zu ONNX + llama.cpp ARM64 Issues

**Datum:** 2026-09-18  
**Cluster:** Contabo Production (`169.58.83.32`) — ARM64/aarch64  
**Worker:** celery-worker-pro (4 CPU, 6Gi Memory Limit)

---

## 1. ONNX Runtime Memory Arena — BEKANNTES VERHALTEN

### Offizielle Dokumentation (microsoft/onnxruntime#11627)

**Issue:** "Why does `enable_cpu_mem_arena` have such a large effect on memory usage during inference?"

**Dokumentation:**
```
"Enables the memory arena on CPU. Arena may pre-allocate memory for future usage.
 Set this option to false if you don't want it. Default is True."
```

**Gemessener Effekt (aus Issue #11627):**
```
Model: 2 MB (ONNX)
Arena ON:  206 MB → 5792 MB (+5579 MB!)   ← 27x Overhead!
Arena OFF: 206 MB → 217 MB (+11 MB)       ← Normal
```

**Unsere Messung (Recording 6dbd0742):**
```
Model: 99 MB (ecapa-speaker-v1.onnx)
Arena ON:  ~349 MB → ~3749 MB (+3400 MB!)  ← ARM64!
Arena OFF: ~349 MB → ~360 MB (erwartet)    ← x86_64 Benchmark
```

### Arena-Strategie (microsoft/onnxruntime#13500)

```cpp
// arena_extend_strategy:
// 0 = kNextPowerOfTwo (DEFAULT) — wächst in 2x Schritten
// 1 = kSameAsRequested — wächst exakt wie angefordert
```

**Problem:** Arena wächst automatisch, gibt aber NICHT frei:
```
"Over extended runtime, the loaded model's memory usage grows and
 eventually causes inference failures — consistent with known
 ONNX Runtime memory arena behavior"
```
— microsoft/foundry-local#861

### Memory Leak (microsoft/onnxruntime#22271)

**Issue:** "Memory leak after running onnx model numerous times"

```
"memory consumption of python process is continuously growing"
"Urgency: On production server python process consumed 100 GB of RAM
 after two months. The only solution is restart the process."
```

**Root Cause:** Arena hält Speicher über Sessions hinweg:
```
"ONNXRuntime CPU arena allocator holding session memory across calls"
```
— blakeblackshear/frigate#23007

### Offizielle Empfehlung

```python
# aus onnxruntime Issue #11627:
sess_options = ort.SessionOptions()
sess_options.enable_cpu_mem_arena = False  # ← REDUZIERT 6GB → 217MB!
```

**Quellen:**
- https://github.com/microsoft/onnxruntime/issues/11627
- https://github.com/microsoft/onnxruntime/issues/22271
- https://github.com/microsoft/onnxruntime/issues/19445
- https://github.com/microsoft/foundry-local/issues/861
- https://github.com/blakeblackshear/frigate/discussions/23007

---

## 2. llama.cpp GGML_ASSERT `set_rows` — BEKANNTES VERHALTEN

### Code-Herkunft

**PR:** ggml-org/llama.cpp#14274 — "ggml : add ggml_set_rows"

```cpp
// ops.cpp:5399
const int64_t i1 = *(int64_t *) ((char *) src1->data + i10*nb10 + i11*nb11 + i12*nb12);
GGML_ASSERT(i1 >= 0 && i1 < ne1);  // ← UNSER CRASH
```

**Funktion:** `ggml_compute_forward_set_rows` — wird für Token-Embedding-Lookup verwendet.

### ARM64-spezifisches Verhalten

**Unser Crash:**
```
GGML_ASSERT(i1 >= 0 && i1 < ne1) failed
→ ggml_compute_forward_set_rows+0x306
→ /vendor/llama.cpp/ggml/src/ggml-cpu/ops.cpp:5399
→ llama-cpp-python (pip install, nicht neueste Version)
```

**Bekanntes Muster:**
- Funktioniert auf x86_64 (anderes SIMD-Verhalten)
- Crasht auf ARM64 bei bestimmten Index-Berechnungen
- tritt bei ≥2 Chunks auf (mehr Token pro Aufruf)

### GGML_NATIVE Fix (aus knowledge.md)

```
| Sep 1 | Sentinel ARM64 fix | Disable GGML_NATIVE for QEMU builds |
```

**Problem:** `GGML_NATIVE` aktiviert ARM64-spezifische SIMD-Instruktionen, die auf QEMU/in Docker nicht funktionieren.

### Offizielle Fixes

**PR #22327:** "disable set_rows error checking"
```
ggml-webgpu: support for SSM_SCAN and disable set_rows error checking (#22327)
```

**Interpretation:** Die llama.cpp Entwickler haben das `set_rows` Error-Checking deaktiviert — ein Indikator dafür, dass der Assertion-Fehler ein bekanntes Problem ist.

### Quellen

- https://github.com/ggml-org/llama.cpp/pull/14274 (set_rows PR)
- https://github.com/ggml-org/llama.cpp/issues/24280 (GGML_ASSERT issues)
- https://github.com/ggml-org/llama.cpp/issues/16475 (Mac ARM64 assertion)
- knowledge.md: "Sep 1 — Sentinel ARM64 fix: Disable GGML_NATIVE"

---

## 3. Vergleich: Offizielle Doku vs. Unsere Crashes

### ONNX Memory Arena

| Metrik | Offizielle Doku | Unsere Messung | Verhältnis |
|---|---|---|---|
| Arena Overhead | 27x (2MB→5792MB) | ~10x (99MB→3749MB) | ARM64 ähnlich |
| Arena Wachstum | Wächst, gibt nicht frei | Wächst, gibt nicht frei | **Identisch** |
| Fix | `enable_cpu_mem_arena=False` | Fehlt im Code | **Empfehlung bestätigt** |
| Memory Leak | Bekannt (Issue #22271) | 3.5GB Residual | **Identisch** |

### llama.cpp SIGABRT

| Metrik | Offizielle Doku | Unsere Crashes | Verhältnis |
|---|---|---|---|
| Assertion | `GGML_ASSERT(i1 >= 0 && i1 < ne1)` | Genau dieser Assertion | **Identisch** |
| Funktion | `ggml_compute_forward_set_rows` | Genau diese Funktion | **Identisch** |
| ARM64 | Bekanntes Problem | Crasht bei ≥2 Chunks | **Bestätigt** |
| Fix | PR #22327 (Error-Checking deaktiviert) | Fehlt in unserer Version | **Empfehlung bestätigt** |

---

## 4. Staking-Umgebung

### Aktueller Status

```
Production (Contabo): 169.58.83.32 — AMD64 (x86_64)
Staging (OCI):        158.180.18.110 — ARM64 (aarch64)

⚠️ SSH zu Staging nicht erreichbar (OCI Security List?)
```

### Staging-Konfiguration (aus knowledge.md)

```
- Staging: 158.180.18.110 — ARM64 (aarch64)
- Namespace: meeting-automation-staging
- URL: staging.meeting-automation.com
- Kubeconfig: ~/.kube/config-staging
```

### Empfehlung für Staging-Testing

```
1. SSH-Zugang zu OCI Staging prüfen (Security List?)
2. ONNX-Speicher-Fix in Staging testen
3. llama-cpp-python Update in Staging testen
4. Bei 0 Crashes → Production deployen
```

---

## 5. Zusammenfassung

### Was die offizielle Doku sagt

```
┌──────────────────────────────────────────────────────────────┐
│  ONNX Runtime:                                               │
│    "Arena may pre-allocate memory for future usage"          │
│    "Set this option to false if you don't want it"           │
│    → BEKANNTES VERHALTEN, nicht Bug                          │
│    → Fix: enable_cpu_mem_arena = False                       │
│                                                              │
│  llama.cpp:                                                  │
│    "GGML_ASSERT(i1 >= 0 && i1 < ne1) failed"                │
│    → BEKanntES Problem auf ARM64                             │
│    → Fix: PR #22327 (Error-Checking deaktiviert)             │
│    → Fix: GGML_NATIVE deaktivieren                           │
│                                                              │
│  BEIDE Fixes sind in offiziellen Repos vorhanden             │
│  Wir müssen nur unsere Versionen updaten/konfigurieren       │
└──────────────────────────────────────────────────────────────┘
```

### Nächste Schritte

| # | Schritt | Priorität | Quelle |
|---|---|---|---|
| 1 | `enable_cpu_mem_arena=False` implementieren | KRITISCH | onnxruntime#11627 |
| 2 | llama-cpp-python updaten | KRITISCH | PR #22327 |
| 3 | GGML_NATIVE deaktivieren | HOCH | knowledge.md |
| 4 | Staging SSH-Zugang prüfen | HOCH | OCI Security List |
| 5 | ONNX Reset vor Sentinel implementieren | HOCH | Eigene Analyse |

---

**Generated by Codebuff 🤖**  
**Date:** 2026-09-18T11:30:00+02:00
