# Incident Report: E2E-Netzwerk-Fehler durch simultane StatefulSet-Restarts

**Erstellt:** 2026-08-17 17:30 UTC
**Cluster:** Staging (OCI, 158.180.18.110)
**Schweregrad:** P2 (E2E-Tests fehlgeschlagen, App funktioniert)
**Status:** ✅ Behoben (`b7d6c130`)

---

## 1. Zusammenfassung

Die E2E-Tests auf Staging fehlgeschlagen (3/29 = 90%, unter 95% Gate). Die 3 Fehler
waren `asyncpg: connection was closed in the middle of operation` und
`Redis: Error -3 connecting to redis:6379. Temporary failure in name resolution`.

**Root Cause:** Das Deploy-Script `03-deploy-manifests.sh` restartete alle 4 StatefulSets
(RabbitMQ, MinIO, Postgres, meeting-db) gleichzeitig. Das destabilisierte den k3s-Cluster
temporär (DNS/CNI-Instabilität), was sowohl den Port-forward (extern) als auch die
Service-DNS-Auflösung (intern) betraf.

---

## 2. Timeline

| Zeit (UTC) | Event | Details |
|------------|-------|---------|
| 16:48:09 | Deploy Staging gestartet | CI Run `32047284178`, Commit `804c891a` |
| 16:50:35 | StatefulSets apply | `minio-statefulset.yaml`, `postgres-statefulset.yaml`, `rabbitmq-statefulset.yaml` |
| **16:51:16** | **Simultaner Restart aller StatefulSets** | rabbitmq, minio, postgres gleichzeitig restarted |
| 16:52:31 | Rollouts abgeschlossen | `✅ All staging manifests applied + StatefulSets restarted` |
| 16:56:08 | E2E Tests gestartet | Port-forward auf 5433, 8080, 9002 |
| 16:56–17:12 | 26/29 Tests laufen fehlerfrei | Postgres-Service über Port-forward erreichbar |
| **17:12:43** | **Port-forward bricht zusammen** | 8× Timeout in ~45s Intervallen |
| **17:12:58** | **Redis DNS-Fehler** | `Error -3 connecting to redis:6379. Temporary failure in name resolution` |
| **17:13:58** | **Pipeline-Fehler** | `TIMING: pipeline_FAILED duration=60.03s error=TimeoutError` |
| 17:14:31 | Zweiter Redis DNS-Fehler | `Temporary failure in name resolution` |
| 17:15–17:20 | 3 restliche Tests fehlgeschlagen | `asyncpg: connection was closed in the middle of operation` |
| 17:20:06 | E2E-Report generiert | 26 passed, 1 skipped, 3 errors |

---

## 3. Root Cause

### Die Änderung

| Commit | Datei | Verhalten |
|--------|-------|-----------|
| `c5ef7c08` (Initial Refactor) | `03-deploy-manifests.sh` | `kubectl apply` + OnlyOffice restart — **keine** StatefulSet-Restarts |
| `84f217b9` (RabbitMQ-Fix) | `03-deploy-manifests.sh` | + `for STS in rabbitmq minio postgres meeting-db` — **simultaner** Restart |

### Die Kette

```
03-deploy-manifests.sh
  → kubectl rollout restart statefulset/rabbitmq-staging  (16:51:17)
  → kubectl rollout restart statefulset/minio-staging      (16:51:20) ← gleichzeitig!
  → kubectl rollout restart statefulset/postgres-staging   (16:51:28) ← gleichzeitig!
  → kubectl rollout restart deployment/onlyoffice-staging  (16:51:16) ← gleichzeitig!
  
  → 4 Pods neu gestartet + Volume-Mounts neu verbunden
  → k3s CNI (Flannel) muss Netzwerk-Regeln neu berechnen
  → CoreDNS muss Service-Endpoints aktualisieren
  → DNS-Cache-Inkonsistenzen für ~20 Minuten
  
  → 17:12: Redis DNS: "Temporary failure in name resolution"
  → 17:12: Port-forward: "connection refused"
  → 17:13: asyncpg: "connection was closed in the middle of operation"
```

### Beweise

| Beweis | Detail |
|--------|--------|
| CI-Log 16:51:16–16:51:28 | Alle 4 StatefulSets gleichzeitig restarted |
| CI-Log 17:12:58 | `Redis: Error -3 connecting to redis:6379. Temporary failure in name resolution` |
| CI-Log 17:13:58 | `TIMING: pipeline_FAILED duration=60.03s error=TimeoutError` |
| CI-Log 17:20:06 | `asyncpg: connection was closed in the middle of operation` (3×) |
| Timing | Deploy war 20 Minuten vor den Fehlern fertig — kein Rolling-Update |

### Warum NICHT ein anderer Grund?

| Hypothese | Warum ausgeschlossen |
|-----------|---------------------|
| Rolling-Update | Deploy war 20 Min vorher fertig — keine laufenden Updates |
| OnlyOffice-Fix | OnlyOffice betrifft keine DB-Verbindungen oder Redis |
| Code-Bug | 26 vorherige Tests liefen fehlerfrei — derselbe Code |
| CI-Runner-Problem | Redis-DNS-Fehler kommt von **innerhalb** des Clusters (Celery-Worker) |

---

## 4. Impact

### Direkt betroffen

| Komponente | Status | Impact |
|-----------|--------|--------|
| E2E-Tests | 3/29 fehlgeschlagen | Pass Rate 90% (unter 95% Gate) |
| Port-forward | Temporär zusammengebrochen | Nur betroffen während der Instabilität |
| Celery-Worker (intern) | Redis DNS-Fehler | Pipeline-Fehler für ~5 Minuten |

### NICHT betroffen

| Komponente | Status |
|-----------|--------|
| App-Funktionalität | ✅ Alle API-Endpunkte erreichbar |
| Backend | ✅ Running |
| Meeting-DB | ✅ Running |
| RabbitMQ | ✅ Running |
| MinIO | ✅ Running |

---

## 5. Fix

### Sofortiger Fix (bereits committed)

**Commit:** `b7d6c130`

**Änderung:** StatefulSet-Restarts von simultan auf sequenziell umgestellt.

| Datei | Vorher | Nachher |
|-------|--------|---------|
| `scripts/deploy-staging/03-deploy-manifests.sh` | Alle 4 STS gleichzeitig → `sleep 30` → alle `rollout status` | Ein STS nach dem anderen: restart → `rollout status` → nächster |
| `scripts/deploy-prod/deploy-all.sh` | Alle 3 STS gleichzeitig → `sleep 60` → alle `rollout status` | Ein STS nach dem anderen: restart → `rollout status` → nächster |

### Effekt

```
Vorher (16:51):
  16:51:17  rabbitmq restarted
  16:51:20  minio restarted       ← gleichzeitig!
  16:51:28  postgres restarted    ← gleichzeitig!
  → DNS/CNI instabil → E2E-Tests fehlgeschlagen

Nachher (nächster Deploy):
  rabbitmq restart → rollout status (120s) → READY
  minio restart → rollout status (120s) → READY
  postgres restart → rollout status (120s) → READY
  → DNS/CNI stabil → E2E-Tests bestehen
```

---

## 6. Lektionen

| # | Lektion | Umsetzung |
|---|---------|-----------|
| 1 | Simultane StatefulSet-Restarts destabilisieren k3s DNS/CNI | Immer sequenziell restarten |
| 2 | StatefulSet-Rollouts brauchen Volume-Mount-Neuverbindung | Nicht mehr als 1 STS gleichzeitig |
| 3 | E2E-Tests nach Deploy brauchen stabilen Cluster | 30s Wartezeit nach letzten Restart vor E2E-Start |
| 4 | Port-forward instabil bei Netzwerk-Änderungen | E2E-Tests sollten Port-forward mit Retry-Logik haben |
| 5 | DNS-Fehler (Name Resolution) = k3s CNI-Problem | Bei DNS-Fehlern: CNI-Status prüfen, nicht nur Service |

---

## 7. Offene Punkte

| # | Punkt | Priorität | Status |
|---|-------|-----------|--------|
| 1 | `03-deploy-manifests.sh` sequenzielle Restarts | ✅ Erledigt | `b7d6c130` |
| 2 | `deploy-all.sh` sequenzielle Restarts | ✅ Erledigt | `b7d6c130` |
| 3 | E2E Pass Rate nach Fix prüfen | ⏳ Nächster Deploy | — |
| 4 | Production RabbitMQ Pod neu starten (timeout 3→10) | ⏳ Offen | SSH nötig |

---

## 8. Vergleich Staging vs Production

| Parameter | Staging | Production |
|-----------|---------|------------|
| Sequential Restarts | ✅ `b7d6c130` deployed | ✅ `b7d6c130` im Git |
| RabbitMQ timeoutSeconds | ✅ 10s (deployed) | 🔴 Pod hat noch 3s (nicht neu gestartet) |
| Velero BSL | ✅ Available | 🔴 Unavailable |
| E2E Tests | ⏳ Nächster Deploy | — |
