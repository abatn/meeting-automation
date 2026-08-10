# CI/CD Workflows — Fakten-basierter Fehlerbericht + Aktionsplan

**Stand:** 2026-08-09
**Basiert auf:** Echten GitHub Actions Logs (nicht Annahmen)

---

## 1. Workflow-Übersicht (IST-Zustand)

| Datei | Trigger | Status (letzter Run) | Datum |
|---|---|---|---|
| `ci.yml` | push main/develop | ✅ **SUCCESS** (Run 31269503995) | 08.08 |
| `deploy-staging.yml` | workflow_run + workflow_dispatch | ✅ **SUCCESS** (letzter nach Fix) | 09.08 |
| `deploy-production.yml` | workflow_dispatch NUR | ❌ **FAILURE** (Run 31305228339) | 09.08 |
| `e2e-tests.yml.disabled` | — | ⏸️ DEAKTIVIERT | 06.08 |

---

## 2. Alle Fehler (mit Beweisen aus Logs)

### 🔴 FEHLER 1: deploy-production.yml — SSH Command Timeout

**Run:** 31305228339 (09.08, 09:09 UTC)
**Beweis (aus Log):**
```
2026-08-09T09:20:00.2448581Z 2026/08/09 09:20:00 Run Command Timeout
2026-08-09T09:20:00.2472312Z ##[error]Process completed with exit code 1.
duration_ms=601520
```

**Root Cause:** `appleboy/ssh-action@v1` hat `command_timeout: 10m` (Default). Das SSH-Script brauchte >600s:
- Backend Image Pull (k3s ctr): **466s** ✅
- Frontend Image Pull (k3s ctr): **Fehler** → `insufficient_scope: authorization failed`
- Frontend Fallback (docker pull): **95s** ✅
- Image Import (docker save | k3s ctr import): **38s** ✅
- **Gesamt: ~600s+ → Timeout BEVOR `kubectl set image` erreicht wurde**

**Effekt:** Frontend + Celery blieben auf altem Image (`bfea2cc7...`). Nur Backend wurde auf `latest` gesetzt.

**Fix:**
```yaml
# deploy-production.yml, Step "Deploy to Contabo Production"
- name: Deploy to Contabo Production
  uses: appleboy/ssh-action@v1
  with:
    command_timeout: 20m  # NEU: 20 Minuten statt 10
```

---

### 🔴 FEHLER 2: deploy-staging.yml — LiveKit YAML-Validierungsfehler (BEHOBEN)

**Run:** 31271332321 (08.08, 18:12 UTC)
**Beweis (aus Log):**
```
error validating "infrastructure/kubernetes/staging/egress-values.yaml": 
  error validating data: [apiVersion not set, kind not set]
error validating "infrastructure/kubernetes/staging/livekit-server-values.yaml": 
  error validating data: [apiVersion not set, kind not set]
Deployment.apps "livekit-server-staging" is invalid: 
  [spec.template.spec.containers[1].ports[1].hostPort: Duplicate value: "TCP//7881",
   spec.selector: Invalid value: field is immutable]
```

**Root Cause:** `kubectl apply -f .../staging/` versuchte Helm-Values-Dateien (kein apiVersion/kind) + alte LiveKit-Deployment-YAMLs (immutable selector) anzuwenden.

**Status:** ✅ **BEHOBEN** in deploy-staging.yml (09.08):
```yaml
# Skip Helm values (livekit-server-values.yaml, egress-values.yaml)
[[ "$fname" == *values*.yaml ]] && continue
# Skip old LiveKit deployment YAMLs (Helm-managed now)
[[ "$fname" == *livekit-*-deployment.yaml ]] && continue
```

---

### 🔴 FEHLER 3: Frontend CI — MeetingRoom.tsx Type-Fehler (BEHOBEN)

**Run:** 31170864748 (07.08, 10:39 UTC)
**Beweis (aus Log):**
```
src/components/meetings/MeetingRoom.tsx(1053,21): error TS2322: 
Type '{ children: Element[]; token: string; serverUrl: string; ... 
onReconnecting: () => void; }' is not assignable to type 
'IntrinsicAttributes & LiveKitRoomProps & { children?: ReactNode; }'
```

**Root Cause:** `LiveKitRoom` in `@livekit/components-react@2.9.21` hat KEINE Props `onReconnecting`/`onReconnected`. Die Props existieren nicht in diesem Version.

**Status:** ✅ **BEHOBEN** (letzte Session):
- Props entfernt
- Reconnect-Zustand via `useConnectionState` Bridge implementiert
- Frontend CI ✅ SUCCESS (Run 31269503970)

---

### 🟡 FEHLER 4: CI Pipeline — Frontend-Fehler blockiert build-and-push

**Run:** 31170864538 (07.08, 10:38 UTC)
**Beweis:** CI Pipeline hängt von `needs: [backend-test, frontend-test]` ab. Frontend-Fehler → CI RED → build-and-push wird NICHT ausgeführt.

**Root Cause:** Gleicher TS2322-Fehler wie Fe#3. Backend-Tests: **304 passed, 64 skipped, 1 xfailed** ✅.

**Status:** ✅ **BEHOBEN** nach TS2322-Fix. CI Pipeline: ✅ SUCCESS (Run 31269503995).

---

### ⚪ FEHLER 5: Codecov Upload — Token fehlt (INFORMATORISCH)

**Run:** 31170864538 (CI Pipeline)
**Beweis:**
```
error - Report creating failed: {"message":"Token required - not valid tokenless upload"}
```

**Root Cause:** `CODECOV_TOKEN` Secret nicht konfiguriert. Tests laufen trotzdem durch.

**Status:** ⚪ Kein Blocker. Nur Coverage-Upload schlägt fehl.

---

## 3. Status pro Workflow

### ✅ ci.yml — FERTIG (kein Action nötig)

| Job | Status | Details |
|---|---|---|
| backend-test | ✅ | 304 passed, 64 skipped, 1 xfailed |
| frontend-test | ✅ | Lint 0 errors, Type-check ✅, Build ✅ |
| build-and-push | ✅ | Multi-Arch Docker Images (amd64+arm64) |

### ✅ deploy-staging.yml — FERTIG (kein Action nötig)

| Job | Status | Details |
|---|---|---|
| pre-flight | ✅ | Image Tag Auflösung |
| deploy-staging | ✅ | Alle Steps (Longhorn, Manifests, Backend, Frontend, Celery, n8n) |
| e2e-test-staging | ✅ | ≥95% Pass Rate Gate |

### ❌ deploy-production.yml — 1 FIX NOCH OFFEN

| Problem | Fix | Priorität |
|---|---|---|
| **SSH Command Timeout** | `command_timeout: 20m` hinzufügen | 🔴 KRITISCH |

**Zusätzliche Optimierung (optional):**
- Frontend Direct Pull Auth-Fehler → Docker-Hub Auth korrigieren oder Fallback beibehalten

---

## 4. Aktionsplan

### Sofort (heute)

| # | Aktion | Datei | Änderung |
|---|---|---|---|
| 1 | **SSH Timeout fixen** | `deploy-production.yml` | `command_timeout: 20m` hinzufügen |
| 2 | **Git push + CI prüfen** | — | Push → CI Pipeline laufen lassen |

### Optional (wenn gewünscht)

| # | Aktion | Datei | Grund |
|---|---|---|---|
| 3 | **Frontend Pull Auth fixen** | `deploy-production.yml` | `k3s ctr images pull` für Frontend schlägt fehl → Fallback funktioniert, aber langsamer |
| 4 | **Codecov Token** | GitHub Secrets | Coverage-Upload |

---

## 5. Zusammenfassung

```
CI/CD Status (2026-08-09):

ci.yml:              ✅ FERTIG — alles grün
deploy-staging.yml:  ✅ FERTIG — alles grün (YAML-Fix eingebaut)
deploy-production.yml: ❌ 1 FIX OFFEN — SSH Timeout (command_timeout: 20m)

Gesamt: 2/3 Workflows funktional, 1 Fix noetig
```
