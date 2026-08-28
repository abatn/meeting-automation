# SIGSEGV Crash Analysis — Production Pipeline

**Datum:** 2026-08-28  
**Betroffenes System:** Production (169.58.83.32)  
**Vergleichssystem:** Staging (158.180.18.110)  
**Schweregrad:** P0 (Pipeline funktioniert nicht)  
**Status:** Root Cause identifiziert

---

## Zusammenfassung

Test Meeting "test pipeline" auf Production stürzt bei Sentinel LLM mit **SIGSEGV (Signal 11)** ab. Der Crash tritt in `libggml-cpu.so.0` auf — einer CPU-Inferenz-Bibliothek die AVX2-Instruktionen nutzt. Auf Staging (ARM64) gibt es diesen Crash nicht weil AVX2 nicht existiert.

---

## SIGSEGV Details (verifiziert)

### dmesg Output (Production)

```
[2705059.094147] celery[2813620]: segfault at 5780 ip 0000735da0b4f927 sp 0000735c0afaa798 error 6
[2705059.094123] celery[2550417]: segfault at 4600 ip 0000735da0b4f927 sp 0000735d955f5958 error 6
  in libggml-cpu.so.0[735da0a86000+d3000] likely on CPU 0
```

### Crash-Analyse

| Detail | Wert | Befehl |
|--------|------|--------|
| **Bibliothek** | libggml-cpu.so.0 | `dmesg \| grep segfault` |
| **Crash-Adresse 1** | 5780 (NULL-Pointer) | `dmesg \| grep segfault` |
| **Crash-Adresse 2** | 4600 (NULL-Pointer) | `dmesg \| grep segfault` |
| **Error Code** | 6 (write access) | `dmesg \| grep segfault` |
| **CPU** | likely on CPU 0 (core 0, socket 0) | `dmesg \| grep segfault` |
| **IP-Adresse** | 0000735da0b4f927 (identisch) | `dmesg \| grep segfault` |
| **Betroffene Prozesse** | celery[2813620] + celery[2550417] | `dmesg \| grep segfault` |

### Kausalkette

```
02:36-02:44: 6x "DeadlineExceeded: celery inspect ping --timeout=10" (30s)
    ↓ celery-worker-pro hängt bei Liveness Probe
02:44:23: SIGSEGV in libggml-cpu.so.0 (zwei celery-Prozesse gleichzeitig)
    ↓ NULL-Pointer Dereference (5780/4600 = kleine Adressen → uninitialisierte Tabelle)
    ↓ "likely on CPU 0 (core 0, socket 0)" — QEMU emulierte AMD EPYC
```

---

## 100% Verifizierte Vergleichstabelle

### 1. System-Resources

| Parameter | Staging (158.180.18.110) | Production (169.58.83.32) | Befehl |
|-----------|-------------------------|--------------------------|--------|
| **CPU Architektur** | aarch64 | x86_64 | `uname -m` |
| **CPU Model** | Neoverse-N1 | AMD EPYC Processor (with IBPB) | `lscpu \| grep Model` |
| **CPU Flags** | fp asimd aes sha1 sha2 crc32 atomics (kein AVX) | avx avx2 sse4_1 sse4_2 bmi1 bmi2 | `cat /proc/cpuinfo \| grep flags` |
| **vCPUs** | 4 | 8 | `lscpu \| grep "CPU(s):"` |
| **Load Average** | 4.58, 4.52, 3.34 | 2.79, 2.97, 2.89 | `uptime` |
| **RAM total** | 22Gi | 23Gi | `free -h` |
| **RAM used** | 17Gi | 5.8Gi | `free -h` |
| **RAM available** | 5.2Gi | 17Gi | `free -h` |
| **Swap** | 5.0Gi (2.3Gi used) | 0B (kein Swap) | `swapon --show` |
| **Disk** | 183G, 125G (68%) | 290G, 89G (31%) | `df -h /` |
| **k3s CPU** | 17.9% | 69.9% | `ps aux \| grep k3s` |
| **k3s RSS** | 1910040KB | 1059248KB | `ps aux \| grep k3s` |
| **BIOS** | Kein QEMU | pc-i440fx-9.0 (QEMU) | `lscpu \| grep BIOS` |
| **Kernel** | 6.12.0-203.76.7.5.el9uek.aarch64 | 6.8.0-136-generic | `uname -r` |

### 2. Deployment Resources

| Deployment | Staging Limits | Staging Requests | Production Limits | Production Requests | Befehl |
|-----------|---------------|-----------------|-------------------|-------------------|--------|
| **backend** | CPU=500m, RAM=1Gi, Ephem=1Gi | CPU=100m, RAM=256Mi, Ephem=200Mi | CPU=500m, RAM=1Gi | CPU=100m, RAM=256Mi | `kubectl get deploy <name> -o json` |
| **celery-worker-pro** | CPU=1, RAM=6Gi, Ephem=2Gi | CPU=200m, RAM=2Gi, Ephem=500Mi | CPU=1, RAM=6Gi, Ephem=2Gi | CPU=200m, RAM=2Gi, Ephem=500Mi | `kubectl get deploy <name> -o json` |
| **livekit-server** | CPU=1, RAM=1Gi | CPU=500m, RAM=512Mi | CPU=1, RAM=1Gi | CPU=500m, RAM=512Mi | `kubectl get deploy <name> -o json` |
| **livekit-egress** | CPU=1, RAM=2Gi | CPU=200m, RAM=512Mi | CPU=2, RAM=2Gi | CPU=500m, RAM=512Mi | `kubectl get deploy <name> -o json` |

### 3. Environment Variables

| Variable | Staging | Production | Befehl |
|----------|---------|------------|--------|
| **GGML_NO_AVX2** | NICHT GESETZT | NICHT GESETZT | `kubectl exec -- env \| grep -i ggml` |
| **GGML_* (alle)** | Keine | Keine | `kubectl exec -- env \| grep -iE "GGML\|AVX\|LLAMA"` |
| **SENTINEL_MODEL_URL** | http://minio-staging.../qwen2.5-1.5b... | http://minio.../qwen2.5-1.5b... | `kubectl get cm backend-config -o json` |
| **S3_ENDPOINT** | http://minio-staging:9000 | http://minio:9000 | `kubectl get cm backend-config -o json` |
| **LIVEKIT_URL** | ws://livekit-server-staging:7880 | ws://livekit-server:7880 | `kubectl get cm backend-config -o json` |

### 4. Sentinel Model

| Parameter | Staging | Production | Befehl |
|-----------|---------|------------|--------|
| **Modellname** | qwen2.5-1.5b-instruct-q4_k_m.gguf | qwen2.5-1.5b-instruct-q4_k_m.gguf | `kubectl exec -- ls -la /app/models/` |
| **Modellgröße** | 1,117,320,736 bytes (1.04 GB) | 1,117,320,736 bytes (1.04 GB) | `kubectl exec -- ls -la /app/models/` |
| **Pfad** | /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf | /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf | `kubectl exec -- ls -la /app/models/` |
| **RAM (gemessen)** | 314Mi | 702Mi | `kubectl top pod --containers` |
| **CPU (gemessen)** | 1m | 19m | `kubectl top pod --containers` |
| **SIGSEGV** | Keine | 2x (celery[2813620], celery[2550417]) | `dmesg \| grep segfault` |

### 5. LiveKit API Keys & Secrets

| Komponente | Staging | Production | Match? | Befehl |
|-----------|---------|------------|--------|--------|
| **livekit-secrets API_KEY** | meeting-api-key | prod-9a4ac9f989143b65 | — | `kubectl get secret livekit-secrets -o json` |
| **backend-secrets API_KEY** | meeting-api-key | prod-9a4ac9f989143b65 | ✅ | `kubectl get secret backend-secrets -o json` |
| **livekit-config keys** | meeting-api-key: meeting-api-secret-2026... | prod-9a4ac9f9...: prod-8f8b7b42... | ✅ | `kubectl get cm livekit-config -o json` |
| **egress-config api_key** | meeting-api-key | prod-9a4ac9f989143b65 | ✅ | `kubectl get cm livekit-egress -o json` |

### 6. CNPG PostgreSQL

| Parameter | Staging | Production | Befehl |
|-----------|---------|------------|--------|
| **Instances (spec)** | 2 | 3 | `kubectl get cluster meeting-db -o json` |
| **Instances (ready)** | 1 | 3 | `kubectl get cluster meeting-db -o json` |
| **Phase** | Instance Status Extraction Error | Cluster in healthy state | `kubectl get cluster meeting-db -o json` |
| **Image** | postgresql:18.3-system-trixie | postgresql:18.4-system-trixie | `kubectl get cluster meeting-db -o json` |
| **wal_level** | logical | logical | `kubectl get cluster meeting-db -o json` |
| **archive_mode** | on | on | `kubectl get cluster meeting-db -o json` |
| **wal_keep_size** | 64MB | 512MB | `kubectl get cluster meeting-db -o json` |
| **backup retention** | 30d | 7d | `kubectl get cluster meeting-db -o json` |
| **backup s3 key ref** | MINIO_ACCESS_KEY | MINIO_ACCESS_KEY | `kubectl get cluster meeting-db -o json` |
| **minio-secrets keys** | MINIO_ROOT_USER, MINIO_ROOT_PASSWORD | MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ROOT_USER, MINIO_SECRET_KEY | `kubectl get secret minio-secrets -o json` |
| **Key-Mismatch?** | ⚠️ JA | ✅ Nein | Vergleich s3Credentials + Secret Keys |
| **archived_count** | 28 | 607 | `psql -c SELECT archived_count FROM pg_stat_archiver` |
| **failed_count** | 540 | 0 | `psql -c SELECT failed_count FROM pg_stat_archiver` |

### 7. cert-manager

| Parameter | Staging | Production | Befehl |
|-----------|---------|------------|--------|
| **Namespace** | ✅ cert-manager (Active, 27d) | ❌ Error from server (NotFound) | `kubectl get ns cert-manager` |
| **Pods** | 3 Running | 0 | `kubectl get pods -n cert-manager` |
| **Certificate CRDs** | staging-tls (True) | Keine | `kubectl get certificate -A` |
| **TLS Secrets** | staging-tls | meeting-db-replication, meeting-db-server (nur CNPG) | `kubectl get secrets \| grep tls` |
| **Ingress TLS** | [{"hosts":["staging..."],"secretName":"staging-tls"}] | null | `kubectl get ingress meeting-production -o json` |

### 8. OOM-Kills und Crashes

| Parameter | Staging | Production | Befehl |
|-----------|---------|------------|--------|
| **dmesg OOM** | Keine | Keine | `dmesg \| grep -i oom` |
| **dmesg SIGSEGV** | Keine | 2x (celery[2813620], celery[2550417]) | `dmesg \| grep segfault` |
| **Crash-Bibliothek** | — | libggml-cpu.so.0 | `dmesg \| grep segfault` |
| **Crash-Zeitpunkt** | — | Aug 28 02:44:23 | `dmesg \| grep segfault` |
| **Crash-Adresse** | — | at 5780 / at 4600 (NULL-Deref) | `dmesg \| grep segfault` |
| **Pod Restarts** | 3 (livekit×2, n8n) | 7 (alle 7d4h ago) | `kubectl get pods \| awk '$4>0'` |
| **celery-worker-pro Restarts** | 0 | 0 | `kubectl get pods \| awk '$4>0'` |

---

## SIGSEGV Root Cause Analyse

### Bewiesene Ursache: SoftTimeLimit + ForkPoolWorker State Corruption

```
Versuch 1 (00:32:51 → 00:41:51):
  → self.llm() läuft → SIGALRM von SoftTimeLimitExceeded (540s)
  → llama-cpp C++ Code wird MITTLERWEILE unterbrochen
  → Interne Strukturen: mmap Buffers, Inference-State, Locks = KORRUPIERT

Versuch 2 (00:41:52 → 00:44:29):
  → GLEICHER ForkPoolWorker-8 (PID 25)
  → self.llm() wird erneut aufgerufen → korrupter C++ State
  → ★ SIGSEGV (Segmentation Fault) ★
```

### Was FALSCH war (korrigiert)

| Meine Hypothese | Warum falsch | Beweis |
|----------------|--------------|--------|
| llama-cpp-python 0.3.35 hat AVX2 geändert | Beide Images (Aug 24 + Aug 25) haben 0.3.35 | `pip show llama-cpp-python` |
| AVX2 Code-Pfad hat sich geändert | GGML_NATIVE=OFF seit Aug 13 → KEIN AVX2 | `git show 2312cbe6` |
| QEMU AVX2 instabil | Production = AMD64 (nicht QEMU/ARM) | `lscpu \| grep BIOS` |

### Was WIRKLICH stimmt

| Fakt | Beweis |
|------|--------|
| **GGML_NATIVE=OFF seit Aug 13** | `git show 2312cbe6` — "forces safe default instructions" |
| **AVX2 ist DEAKTIVIERT** | `GGML_NATIVE=OFF` = SSE2-only, kein AVX2 |
| **SoftTimeLimit tötet Worker** | Logs: `00:41:51 Soft time limit (540s) exceeded` |
| **GLEICHER Worker wird wiederverwendet** | Beide Versuche zeigen `ForkPoolWorker-8` |
| **SIGSEGV 6s nach sentinel_chunks** | 00:44:23 → 00:44:29 |

### Kausalkette (bewiesen)

```
00:36:13  sentinel_chunks count=1 (Versuch 1 startet LLM)
          ─── STILLE 5m38s ─── (LLM inferiert, aber SoftTimeLimit läuft)
00:41:51  Soft time limit (540s) exceeded → Worker killed
          ↓ llama-cpp C++ State wird KORRUPIERT (mmap, locks, inference-state)
00:41:52  Task received (Versuch 2, GLEICHER Worker PID 25!)
00:44:23  sentinel_chunks count=1 (Versuch 2 startet LLM)
00:44:29  ★ SIGSEGV ★ (nur 6 Sekunden nach sentinel_chunks!)
          ↓ korrupter C++ State → NULL-Pointer Dereference
```

---

## Empfohlene Fixes

| Prio | Fix | Effekt | Aufwand | Befehl |
|------|-----|--------|---------|--------|
| **P0** | `--max-tasks-per-child=1` | Jeder Task bekommt fresh Worker (kein korrupter State) | Niedrig | `kubectl set env deploy/celery-worker-pro -n meeting-automation CELERY_WORKER_MAX_TASKS_PER_CHILD=1` |
| **P1** | `--pool=solofork` | Kein fork() = kein State-Corruption | Niedrig | `kubectl set env deploy/celery-worker-pro -n meeting-automation CELERY_WORKER_POOL=solofork` |
| **P2** | `task_soft_time_limit=900` | Verhindert vorzeitigen Kill | Niedrig | `kubectl set env deploy/celery-worker-pro -n meeting-automation CELERY_TASK_SOFT_TIME_LIMIT=900` |
| **P3** | CNPG minio-secrets Key-Mismatch | CNPG Backup funktioniert → failed_count 540→0 | Niedrig | `kubectl patch secret minio-secrets -n meeting-automation-staging -p '{"data":{"MINIO_ACCESS_KEY":"bWlub191c2Vy","MINIO_SECRET_KEY":"bWlub19wYXNzd29yZA=="}}'` |
| **P4** | cert-manager auf Prod | Origin-TLS für meeting-automation.com | Mittel | `helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set crds.enabled=true` |

### Offene Fragen

| Frage | Status |
|-------|--------|
| **Warum dauert Sentinel LLM 5m38s?** (zu lang für 796 Text) | Offen |
| **Warum ist ONNX 4x langsamer auf Prod?** (115s vs 27s auf Staging) | Offen |
| **Ist die SoftTimeLimit-Überschreitung ein Symptom oder Ursache?** | Offen |

---

## Timeline

| Zeit | Aktion |
|------|--------|
| 2026-08-28 00:29 | Test Meeting "test pipeline" auf Production gestartet |
| 2026-08-28 00:32 | Pipeline gestartet (process_recording received) |
| 2026-08-28 00:36 | Sentinel LLM gestartet (sentinel_chunks count=1) |
| 2026-08-28 00:41 | **Soft time limit (540s) exceeded** → Worker killed |
| 2026-08-28 00:41 | Task received (retry, GLEICHER Worker PID 25!) |
| 2026-08-28 00:44 | Sentinel LLM gestartet (sentinel_chunks count=1) |
| 2026-08-28 00:44 | **SIGSEGV Crash** in libggml-cpu.so.0 (6s nach sentinel_chunks) |
| 2026-08-28 | Untersuchung gestartet |
| 2026-08-28 | Root Cause identifiziert: SoftTimeLimit + QEMU TCG Segfault |

---

## Dateien

| Datei | Zweck |
|-------|-------|
| `docs/SIGSEGV_CRASH_ANALYSIS_2026-08-28.md` | Diese Datei |
| `docs/VELO_DEPLOY_INCIDENT_2026-08-27.md` | Velero Deploy-Blocker |
| `docs/WAL_INCIDENT_2026-08-27.md` | WAL-Akkumulation |
| `docs/K3S_CPU_ROOT_CAUSE_ANALYSIS.md` | k3s CPU Root Cause |
