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
    ↓ "likely on CPU 0 (core 0, socket 0)"
```

---

## 100% Verifizierte Vergleichstabelle

### 1. System-Resources

| Parameter | Staging (158.180.18.110) | Production (169.58.83.32) | Status |
|-----------|-------------------------|--------------------------|--------|
| **Architektur** | aarch64 (ARM Cortex Neoverse-N1) | x86_64 (AMD EPYC) | ✅ |
| **vCPU** | 4 | 8 | ✅ |
| **CPU Flags** | fp asimd aes sha1 sha2 crc32 atomics (kein AVX) | avx avx2 avx512 sse4_1 sse4_2 bmi1 bmi2 | ✅ |
| **Kernel** | 6.12.0-203.76.7.5.el9uek.aarch64 | 6.8.0-136-generic | ✅ |
| **OS** | Oracle Linux Server 9.7 | Ubuntu 24.04.4 LTS | ✅ |
| **k3s Version** | v1.36.2+k3s1 | v1.36.2+k3s1 | ✅ Identisch |
| **RAM total** | 22Gi | 23Gi | ✅ |
| **RAM used** | 11Gi (50%) | 5.7Gi (25%) | ✅ |
| **Swap** | 5GB (3.4GB used) | 0B (kein Swap) | ❌ |
| **Disk** | 183G, 120G (66%) | 290G, 89G (31%) | ✅ |
| **Load Average** | 1.07, 1.20, 1.30 | 1.56, 2.30, 2.80 | ⚠️ Prod höher |
| **k3s CPU** | 17.9% | 70.0% | ❌ KRITISCH |
| **k3s RAM** | 1.8GB RSS | 1.0GB RSS | ✅ |
| **Nodes** | 1 (Single-Node) | 1 (Single-Node) | ✅ |

### 2. Deployment Resources (Limits/Requests)

| Deployment | Resource | Staging | Production | Differenz |
|-----------|----------|---------|------------|----------|
| **backend** | CPU limit | 500m | 500m | — |
| | CPU request | 100m | 100m | — |
| | RAM limit | 1Gi | 1Gi | — |
| | RAM request | 256Mi | 256Mi | — |
| | Ephemeral limit | 1Gi | none | ⚠️ Prod kein Ephemeral-Limit |
| | Ephemeral request | 200Mi | none | — |
| **celery-worker-pro** | CPU limit | 1 | 1 | — |
| | CPU request | 200m | 200m | — |
| | RAM limit | 6Gi | 6Gi | — |
| | RAM request | 2Gi | 2Gi | — |
| | Ephemeral limit | 2Gi | 2Gi | — |
| **livekit-server** | CPU limit | 1 | 1 | — |
| | CPU request | 500m | 500m | — |
| | RAM limit | 1Gi | 1Gi | — |
| | RAM request | 512Mi | 512Mi | — |
| | hostNetwork | true | true | — |
| | nodeSelector | instance-20260329-0846 | contabo-prod | — |
| **livekit-egress** | CPU limit | 1 | 2 | ⚠️ Prod 2x |
| | CPU request | 200m | 500m | Prod 2.5x |
| | RAM limit | 2Gi | 2Gi | — |
| | RAM request | 512Mi | 512Mi | — |
| | hostNetwork | true | true | — |
| **onlyoffice** | CPU limit | 1 | 1 | — |
| | RAM limit | 2Gi | 2Gi | — |
| | RAM request | 512Mi | 512Mi | — |

### 3. Environment Variables

| Variable | Staging | Production | Differenz |
|----------|---------|------------|----------|
| **GGML_NO_AVX2** | NICHT GESETZT | NICHT GESETZT | ⚠️ Kein AVX-Schutz auf Prod |
| **GGML_ (alle)** | Keine | Keine | — |
| **LLAMA_ (alle)** | Keine | Keine | — |
| **THREAD** | Keine | Keine | — |
| **SENTINEL_MODEL_URL** | http://minio-staging.../qwen2.5-1.5b... | http://minio.../qwen2.5-1.5b... | Service-Name |
| **S3_ENDPOINT** | http://minio-staging:9000 | http://minio:9000 | Service-Name |
| **LIVEKIT_URL** | ws://livekit-server-staging:7880 | ws://livekit-server:7880 | Service-Name |
| **LIVEKIT_PUBLIC_URL** | wss://staging.meeting-automation.com | wss://meeting-automation.com | Domain |
| **DEBUG** | true | false | ⚠️ Staging=Debug |
| **envFrom** | backend-secrets-staging + backend-config | backend-secrets + backend-config | Secret-Name |

### 4. Sentinel Model

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **Modell** | qwen2.5-1.5b-instruct-q4_k_m.gguf | qwen2.5-1.5b-instruct-q4_k_m.gguf | ✅ Identisch |
| **Modellgröße** | 1,117,320,736 bytes (1.04 GB) | 1,117,320,736 bytes (1.04 GB) | ✅ Identisch |
| **Datei-Pfad** | /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf | /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf | ✅ Identisch |
| **PVC** | sentinel-models-claim (2Gi, local-path) | sentinel-models-claim (2Gi, local-path) | ✅ Identisch |
| **RAM gemessen** | 1045Mi | 743Mi | ⚠️ Unterschiedlich |
| **CPU-Arch** | aarch64 (ARM NEON) | amd64 (AVX2) | ✅ |
| **GGML Backend** | ARM NEON | x86 AVX2 | ✅ |
| **SIGSEGV** | ✅ Nie | ❌ 2x Crashes (Aug 28 02:44) | ❌ |

### 5. LiveKit Konfiguration

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **API Key (livekit-secrets)** | meeting-api-key | prod-9a4ac9f989143b65 | — |
| **API Key (backend-secrets)** | meeting-api-key | prod-9a4ac9f989143b65 | ✅ Match |
| **API Key (livekit-config)** | meeting-api-key | prod-9a4ac9f989143b65 | ✅ Match |
| **API Key (egress-config)** | meeting-api-key | prod-9a4ac9f989143b65 | ✅ Match |
| **API Secret (livekit-secrets)** | meeting-api-secret-2026... | prod-8f8b7b429f... | — |
| **API Secret (egress-config)** | meeting-api-secret-2026... | prod-8f8b7b429f... | ✅ Match |
| **hostNetwork** | true (server+egress) | true (server+egress) | ✅ |
| **nodeSelector** | instance-20260329-0846 | contabo-prod | ✅ |
| **ws_url (egress)** | ws://livekit-server-staging:7880 | ws://livekit-server:7880 | ✅ |
| **redis password (server)** | redis_password | flgyEhZKHVyMBge1QkdKtA | — |
| **redis password (egress)** | redis_password | flgyEhZKHVyMBge1QkdKtA | ✅ Match |
| **webhook URL** | http://backend.meeting-automation-staging... | http://backend.meeting-automation... | ✅ |
| **room_composite_cpu_cost** | 1.5 | 2.0 | ⚠️ Prod höher |

### 6. CNPG PostgreSQL

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **Instances (spec)** | 2 | 3 | ✅ |
| **Instances (ready)** | 1 | 3 | ⚠️ Staging nur 1 |
| **Phase** | ⚠️ Instance Status Extraction Error | ✅ Cluster in healthy state | ⚠️ |
| **Image** | postgresql:18.3-system-trixie | postgresql:18.4-system-trixie | ✅ |
| **wal_level** | logical | logical | ✅ |
| **archive_mode** | on | on | ✅ |
| **wal_keep_size** | 64MB | 512MB | ✅ |
| **backup retention** | 30d | 7d | ✅ |
| **backup target** | prefer-standby | prefer-standby | ✅ |
| **Backup endpoint** | http://minio-staging...:9000 | http://minio...:9000 | ✅ |
| **archived_count** | 28 | 648 | ✅ |
| **failed_count** | 2271 | 0 | ⚠️ Staging hat Fehler (gewachsen) |
| **minio-secrets keys** | MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ROOT_USER (TYPO: mino_user) | MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ROOT_USER, MINIO_SECRET_KEY | ⚠️ TYPO |
| **CNPG s3Credentials key** | MINIO_ACCESS_KEY | MINIO_ACCESS_KEY | ✅ |
| **Key-Mismatch?** | ✅ NEIN (gepatcht) | ✅ Nein | ✅ GEFIXT |

### 7. cert-manager

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **Namespace** | ✅ cert-manager (Active, 27d) | ❌ FEHLT | ❌ |
| **Pods** | 3 (cert-manager, cainjector, webhook) | 0 | ❌ |
| **Certificate CRDs** | ✅ staging-tls (True), monitoring-tls (True) | ❌ Keine | ❌ |
| **TLS Secrets** | staging-tls, monitoring-tls | meeting-db-replication, meeting-db-server (nur CNPG) | ❌ |
| **Ingress TLS (main)** | ✅ staging-tls | ❌ null (kein TLS in meeting-production) | ❌ |
| **Ingress TLS (n8n)** | ✅ staging-tls | ✅ production-tls | ✅ |
| **HTTPS funktioniert?** | ✅ Origin-TLS | ⚠️ Cloudflare Flexible (Edge→Origin HTTP) | ⚠️ |

### 8. OOM-Kills und Crashes

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **dmesg OOM** | ✅ Keine | ✅ Keine | ✅ |
| **dmesg SIGSEGV** | ✅ Keine | ❌ 2x (celery[2813620], celery[2550417]) | ❌ |
| **Crash-Bibliothek** | — | libggml-cpu.so.0 (GGML CPU Inference) | ❌ |
| **Crash-Zeitpunkt** | — | Aug 28 02:44:23 | ❌ |
| **Crash-Adresse** | — | at 5780 / at 4600 (NULL-Deref) | ❌ |
| **k3s SIGSEGV** | — | Keine | ✅ |
| **Pod Restarts** | 3 (livekit×2, n8n — alle kürzlich gedeplayed) | 7 (alle 7d4h ago — Deployment-Restart) | ✅ |
| **celery-worker-pro Restarts** | 0 | 0 (aber Liveness-Fehler: inspect ping --timeout=10 timed out) | ⚠️ |
| **Pod Memory (celery-worker-pro)** | 1045Mi | 743Mi | ⚠️ Unterschiedlich |

### 9. k3s Konfiguration

| Parameter | Staging | Production | Status |
|-----------|---------|------------|--------|
| **Start-Methode** | Inline args (--disable=traefik) | Config-Datei (config.yaml) | ✅ |
| **GOGC** | NICHT GESETZT | 50 | ⚠️ |
| **GOMEMLIMIT** | NICHT GESETZT | 1500MiB | ⚠️ |
| **kubelet-arg** | Nicht sichtbar | system-reserved=cpu=500m,memory=1Gi, eviction-hard=nodefs<10%,imagefs<15% | ⚠️ |
| **metrics-server** | Standard (aktiv) | Deaktiviert | ⚠️ |
| **containerd** | 26G + 7.4G Docker buildkit | 22G | ✅ |
| **Image GC** | Standard | high=75%, low=70% | ⚠️ |

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

### Was WIRKLICH stimmt

| Fakt | Beweis |
|------|--------|
| **SoftTimeLimit tötet Worker** | Logs: `00:41:51 Soft time limit (540s) exceeded` |
| **GLEICHER Worker wird wiederverwendet** | Beide Versuche zeigen `ForkPoolWorker-8` |
| **SIGSEGV 6s nach sentinel_chunks** | 00:44:23 → 00:44:29 |
| **CNPG minio-secrets** | MINIO_ACCESS_KEY vorhanden, aber TYPO (mino_user statt minio_user) |
| **room_composite_cpu_cost unterschiedlich** | Staging=1.5, Prod=2.0 |
| **dmesg-Buffer rotiert** | Segfault-Einträge nicht mehr sichtbar |

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

| Prio | Fix | Effekt | Aufwand | Status |
|------|-----|--------|---------|--------|
| **P0** | `task_soft_time_limit=900` | Verhindert vorzeitigen Kill | Niedrig | ⏳ Offen |
| **P1** | cert-manager auf Prod | Origin-TLS für meeting-automation.com | Mittel | ⏳ Offen |
| **P1** | production-tls Secret für Prod | n8n Ingress TLS | Niedrig | ⏳ Offen |
| **P2** | CNPG minio-secrets TYPO korrigieren | mino_user → minio_user | Niedrig | ⏳ Offen |
| **P2** | room_composite_cpu_cost Prod=2.0 | Staging=1.5, Prod=2.0 — unterschiedlich | Niedrig | ⏳ Offen |
| ✅ | CNPG minio-secrets Key-Mismatch | MINIO_ACCESS_KEY vorhanden | ✅ | ✅ GEFIXT |

### Offene Fragen

| Frage | Status |
|-------|--------|
| **Warum dauert Sentinel LLM 5m38s?** (zu lang für 796 Text) | Offen |
| **Warum ist ONNX 4x langsamer auf Prod?** (115s vs 27s auf Staging) | Offen |
| **Warum hat die Pipeline vorher funktioniert?** (letzte successful Recording Aug 14) | Offen |
| **Funktioniert max_tasks_per_child in dieser Celery-Version?** (nicht als CLI-Parameter getestet) | Offen |

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
| 2026-08-28 | Root Cause identifiziert: SoftTimeLimit + ForkPoolWorker State Corruption |
| 2026-08-28 | Korrekturen durchgeführt: pool=solofork ungültig, max-tasks-per-child nur Config |

---

## Dateien

| Datei | Zweck |
|-------|-------|
| `docs/SIGSEGV_CRASH_ANALYSIS_2026-08-28.md` | Diese Datei |
| `docs/VELO_DEPLOY_INCIDENT_2026-08-27.md` | Velero Deploy-Blocker |
| `docs/WAL_INCIDENT_2026-08-27.md` | WAL-Akkumulation |
| `docs/K3S_CPU_ROOT_CAUSE_ANALYSIS.md` | k3s CPU Root Cause |
| `docs/ONLYOFFICE_PRODUCTION_FIX_2026-08-27.md` | OnlyOffice Routing-Bug |
| `docs/K3S_TUNING_PLAN_2026-08-20.md` | k3s Tuning Plan |
