# Production LiveKit Helm Migration — Plan & Staging-Abgleich (2026-08-08, abgeschlossen 2026-08-09)

**Erstellt:** 2026-08-08 · **Abgeschlossen:** 2026-08-09 (Gate 4 E2E bestanden, Phase 4c Disk-Stabilisierung)
**Ziel:** Production (`meeting-automation` / Contabo `169.58.83.32`) 100% auf Helm wie Staging bringen — ohne Ausfall.
**Ausgangslage:** Production lief seit 12 Tagen stabil mit **direkten YAML-Deployments** (OLD-Labels `app:`). Die Repo-Dateien für Helm-Values existierten, waren aber **nicht chart-konform** und hätten bei einem CI/CD-Deploy Production gebrochen.

---

## Inhaltsverzeichnis

1. [Ist-Zustand Production (live)](#1-ist-zustand-production-live)
2. [Staging vs. Production — 100%-Ähnlichkeitscheck](#2-staging-vs-production--100-ähnlichkeitscheck)
3. [Kritische Blocker (müssen vor Deploy gefixt werden)](#3-kritische-blocker-müssen-vor-deploy-gefixt-werden)
4. [Migrationsplan (Phasen 0–4)](#4-migrationsplan-phasen-04)
5. [Verifikation (Gates)](#5-verifikation-gates)
6. [Rollback](#6-rollback)
7. [Offene Punkte / Entscheidungen](#7-offene-punkte--entscheidungen)

---

## 1. Ist-Zustand Production (live)

| Komponente | Status | Beweis (gemessen) |
|---|---|---|
| **LiveKit Server** | ✅ läuft, 12d | Deployment `livekit-server`, Labels `app: livekit-server` |
| **LiveKit Egress** | ✅ läuft, 12d | Deployment `livekit-egress`, Labels `app: livekit-egress` |
| **Service-Endpoints** | ✅ **VORHANDEN** | `169.58.83.32:7881, 169.58.83.32:7880` — **kein Staging-Endpoints-Bug** |
| **Backend → Service** | ✅ OK | python-Test: `OK: Service erreichbar` (`ws://livekit-server:7880`) |
| **Backend → NodeIP** | ✅ OK | `OK: NodeIP 169.58.83.32:7880` |
| **hostNetwork** | ✅ beide true | Server + Egress |
| **NetworkPolicies** | ✅ konsistent (OLD-Labels) | 15 Policies, alle `app:` → matchen echte Pods |
| **Ingress** | ✅ | `/rtc` + `/twirp` → `livekit-server:7880`, `/livekit` → backend |
| **Egress ws_url** | ✅ | `ws://livekit-server:7880` |
| **CPU-Last** | ✅ minimal | Server 6m, Egress 39m |
| **Helm-Releases** | ❌ KEINE | `helm list -A` → nur cnpg, nginx, prometheus, longhorn |

**Warum funktioniert Production, obwohl Staging kaputt war?**
Weil Production **nie den Helm-Umstieg gemacht hat**: Pods, Service-Selector UND NetworkPolicies tragen alle konsistent das OLD-Label `app:` → alles matcht. Der Staging-Endpoints-Bug (0 Endpoints über 46h) entstand erst durch den Helm-Umstieg, bei dem die Pods neue Labels bekamen, der Service aber das alte behielt.

---

## 2. Staging vs. Production — 100%-Ähnlichkeitscheck

### 2.1 Helm Values: `livekit-server-values.yaml`

| Feld | Staging (funktionierend) | Production (Repo, fehlerhaft) | Ähnlich? | Fix |
|---|---|---|---|---|
| Top-Level-Schema | `livekit:` | ❌ `config:` | **NEIN** | `config:` → `livekit:` |
| `nameOverride` | `livekit-config-staging` | `livekit-server` | ✅ (Namensunterschied ok) | — |
| `fullnameOverride` | `livekit-config-staging` | `livekit-server` | ✅ (Namensunterschied ok) | — |
| `livekit.port` | `7880` | (unter config) | — | übernehmen |
| `livekit.rtc.tcp_port` | `7881` | (unter config) | — | übernehmen |
| `livekit.rtc.port_range_start/end` | `50000/60000` | (unter config) | — | übernehmen |
| `livekit.rtc.use_external_ip` | `true` | (unter config) | — | übernehmen |
| `force_tcp` / `allow_tcp_fallback` / `tcp_fallback_rtt_threshold` | **NICHT enthalten** (Chart kennt sie nicht, Staging-Lesson #4) | ❌ enthalten | **NEIN** | **entfernen** |
| `ping_interval` | nicht gesetzt | ❌ `5` | **NEIN** | **entfernen** (kein Chart-Key) |
| `livekit.redis.address` | `redis-staging...:6379` | `redis.meeting-automation.svc...:6379` | ✅ (Env-Unterschied) | — |
| `livekit.redis.password` | `redis_password` | `flgyEhZKHVyMBge1QkdKtA` | ✅ (Env-Unterschied) | — |
| `livekit.keys` | `meeting-api-key: ...` | `prod-9a4ac9f989143b65: prod-...` | ✅ (Env-Unterschied) | — |
| `livekit.turn.enabled` | ❌ `false` (TURN ohne TLS = 403, Staging-Lesson #5) | ❌ `true` | **NEIN** | `false` |
| `livekit.turn.udp_port` | nicht gesetzt | ❌ `3478` | **NEIN** | **entfernen** (bei turn disabled) |
| `livekit.webhook.api_key` | `meeting-api-key` | `prod-...` | ✅ (Env) | — |
| `livekit.webhook.urls` | backend-staging | backend-prod | ✅ (Env) | — |
| `loadBalancer.type` | `disable` | ❌ **fehlt** | **NEIN** | `type: disable, servicePort: 7880` |
| `podHostNetwork` | `true` | `true` | ✅ | — |
| `dnsPolicy` | **NICHT als Value** (Chart setzt selbst) | ❌ `ClusterFirstWithHostNet` als Value | **NEIN** | **entfernen** |
| `deploymentStrategy.type` | `Recreate` | `Recreate` | ✅ | — |
| `nodeSelector` | `kubernetes.io/hostname: instance-20260329-0846` (Staging-Node) | ❌ fehlt | **NEIN** (Production braucht Prod-Node-Name) | ergänzen |
| `resources.limits.cpu` | `1000m` | ❌ `1000m` | **NEIN** | `1000m` |
| `resources.limits.memory` | `1024Mi` | `1024Mi` | ✅ | — |
| `resources.requests` | `500m/512Mi` | `500m/512Mi` | ✅ | — |
| `autoscaling` | `enabled: false` | ❌ fehlt | **NEIN** | ergänzen |
| `serviceMonitor.create` | `false` | ❌ fehlt | **NEIN** | ergänzen |
| `service:` (ClusterIP) | **NICHT als Value** (Chart nutzt `loadBalancer`) | ❌ vorhanden | **NEIN** | **entfernen** |
| `livenessProbe` / `readinessProbe` | **NICHT als Value** (kein Chart-Key) | ❌ vorhanden | **NEIN** | **entfernen** |
| `podSecurityContext` / `securityContext` | `{}` | fehlt | **NEIN** | ergänzen (optional) |

### 2.2 Helm Values: `egress-values.yaml`

| Feld | Staging | Production | Ähnlich? | Fix |
|---|---|---|---|---|
| Schema `egress:` | ✅ | ✅ | **JA** | — |
| `ws_url` | `ws://livekit-config-staging:7880` | `ws://livekit-server:7880` | ✅ (Env) | — |
| `api_key` / `api_secret` | `meeting-api-key` | `prod-...` | ✅ (Env) | — |
| `redis` | staging | prod | ✅ (Env) | — |
| `s3` | staging (minio-staging) | prod (minio) | ✅ (Env) | — |
| `resources` | `200m/512Mi` req, `1/2Gi` lim | identisch | ✅ | — |
| `deploymentStrategy` | `Recreate` | `Recreate` | ✅ | — |
| `hostNetwork`-Doku | ✅ | ✅ | **JA** | — |
| **Verdikt** | — | **chart-konform** | ✅ **100%** | keine Fixes nötig |

### 2.3 NetworkPolicies

| Policy | Staging (funktionierend) | Production (Repo) | Ähnlich? | Fix |
|---|---|---|---|---|
| `livekit-policy` podSelector | `app.kubernetes.io/name: livekit-config-staging` | ❌ `app.kubernetes.io/name: livekit-server` (nur Helm-Label) | ⚠️ | **Transition:** OLD-Policy `app: livekit-server` BEHALTEN + NEUE `livekit-policy-helm` HINZUFÜGEN (podSelector kann kein OR) |
| `livekit-egress-policy` podSelector | `app.kubernetes.io/name: egress` | ❌ `app.kubernetes.io/name: egress` (nur Helm-Label) | ⚠️ | gleiche Transition wie oben |
| `minio-policy` (Egress → MinIO) | ✅ Egress-Pod in from-Liste | ❌ **Egress fehlt** in `from` | **NEIN** | `app.kubernetes.io/name: egress` ergänzen |
| `redis-policy` | ✅ Egress enthalten | ✅ `app: livekit-egress` + `app: livekit-server` | ⚠️ | Helm-Label zusätzlich ergänzen |

### 2.4 Maschineller Vergleich (2026-08-08, `python3 compare_values.py`)

Programmatischer Key-Strukturvergleich beider Values-Dateien (YAML-Parsing, alle verschachtelten Keys):

| Datei | Staging-Keys | Prod-Keys | Gemeinsam | Ergebnis |
|---|---|---|---|---|
| `livekit-server-values.yaml` | 49 | 57 | 13 | ❌ **36 Staging-Keys fehlen, 44 Production-only** (falsches `config:`-Schema + nicht unterstützte Keys) |
| `egress-values.yaml` | 44 | 44 | **44** | ✅ **100% strukturell identisch** — nur Env-Werte (Credentials, URLs) unterscheiden sich |

**Livekit-Server — die 36 fehlenden Staging-Keys (Auszug):** `livekit.*` (kompletter Block), `image.*`, `loadBalancer.*`, `nodeSelector.*`, `autoscaling.*`, `serviceMonitor.*`, `podSecurityContext`, `securityContext`

**Livekit-Server — die 44 Production-only-Keys (Auszug):** `config.*` (kompletter Block statt `livekit:`), `dnsPolicy`, `livenessProbe.*`, `readinessProbe.*`, `service.*`

**Wert-Abweichung bei gemeinsamen Keys:** `resources.limits.cpu` = staging `1000m` vs. prod `1000m` ❌

**Fazit:** `livekit-server-values.yaml` ist **nicht chart-konform** und muss vollständig auf das Staging-Schema umgebaut werden (Phase 0.1). `egress-values.yaml` ist bereits 100% konform.

### 2.5 CI/CD (`deploy-production.yml`)

| Schritt | Aktuell | Problem | Fix |
|---|---|---|---|
| `kubectl apply -f network-policies.yaml` (Zeile 114) | VOR Helm | Policies mit Helm-Labels matchen OLD-Pods nicht → **Production abgeschnitten** | NetworkPolicies-Zeile muss nach der Helm-Phase kommen ODER Transition-Policies (beide Label-Systeme) verwenden |
| `helm upgrade livekit-server` (Zeile 127) | — | Kein Release vorhanden → `helm upgrade` auf nicht-existierendes Release legt neues an; Deployment-Name kollidiert mit bestehendem OLD-Deployment | Erst OLD-Deployments löschen, dann `helm upgrade --install` |
| hostNetwork-Patch | ✅ vorhanden | — | bleibt |

---

## 3. Kritische Blocker (müssen vor Deploy gefixt werden)

> **Verifiziert durch maschinellen Vergleich (Abschnitt 2.4):** Die Abweichungen sind nicht nur dokumentiert, sondern programmatisch nachgewiesen (36 fehlende + 44 Production-only-Keys).

1. **`livekit-server-values.yaml` falsches Schema** (`config:` statt `livekit:`) → Server startet mit Default-Config (keine Keys, kein Redis, kein Webhook) → **kompletter Ausfall**
2. **Nicht unterstützte Chart-Keys** (`service:`, `livenessProbe:`, `readinessProbe:`, `dnsPolicy:`, `force_tcp`, `ping_interval`) → werden ignoriert oder brechen das Rendering
3. **`turn.enabled: false` ohne TLS** → bekannter `403 CreatePermission` (Staging-Lesson #5)
4. **NetworkPolicies podSelectors nur Helm-Label** → matchen OLD-Pods nicht → `default-deny-all` schneidet LiveKit ab
5. **`minio-policy` fehlt Egress** → Egress kann Recordings nicht hochladen
6. **Deployment-Selektoren immutable** → OLD-Deployments müssen vor Helm-Install gelöscht werden (Wartungsfenster)
7. **CI/CD-Reihenfolge** → NetworkPolicies dürfen nicht vor Helm mit Helm-Labels deployed werden

---

## 4. Migrationsplan (Phasen 0–4)

### Phase 0 — Repo vorbereiten (kein Cluster-Eingriff)

| # | Datei | Änderung |
|---|---|---|
| 0.1 | `production/livekit-server-values.yaml` | `config:` → `livekit:`; entferne `service:`/`livenessProbe:`/`readinessProbe:`/`dnsPolicy:`/`force_tcp`/`allow_tcp_fallback`/`tcp_fallback_rtt_threshold`/`ping_interval`; `turn.enabled: false`; CPU `1000m`; `loadBalancer: {type: disable, servicePort: 7880}`; `autoscaling`, `serviceMonitor`, `nodeSelector` ergänzen |
| 0.2 | `production/network-policies.yaml` | OLD-Policies behalten + `livekit-policy-helm` + `livekit-egress-policy-helm` HINZUFÜGEN; `minio-policy` um `app.kubernetes.io/name: egress` ergänzen |
| 0.3 | `production/egress-values.yaml` | ✅ bereits konform — nur verifizieren |
| 0.4 | Validierung | `helm template` lokal rendern + gegen Chart-Schema prüfen |

**Gate 0:** `helm template livekit-server -f production/livekit-server-values.yaml` rendert gültige ConfigMap mit `port: 7880` + `keys: prod-...`.

### Phase 1 — Übergangspolicies aktivieren (NICHT-disruptiv)

```bash
kubectl apply -f production/network-policies.yaml
```
Nur **hinzufügen** — OLD-Policies bleiben. Kein Pod/Service/Deployment wird angefasst. LiveKit läuft weiter.

**Gate 1:** `kubectl get networkpolicy` → 15 alte + 2 neue. Endpoints weiterhin da.

### Phase 2 — Helm-Migration (Wartungsfenster, ~2–3 Min LiveKit-Downtime)

> ⚠️ Deployment-Selektoren sind immutable → OLD-Deployments löschen, bevor Helm neue anlegt. Nur außerhalb aktiver Meetings.

```bash
# 1. Alte Direkt-YAML-Deployments entfernen (nur LiveKit!)
kubectl delete deployment livekit-server livekit-egress -n meeting-automation

# 2. Helm installieren
helm install livekit-server livekit/livekit-server -n meeting-automation \
  -f production/livekit-server-values.yaml
helm install livekit-egress livekit/livekit-egress -n meeting-automation \
  -f production/egress-values.yaml

# 3. hostNetwork-Patch (Chart rendert es nicht aus Values — Staging-Lesson)
kubectl patch deployment livekit-server -n meeting-automation --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl patch deployment livekit-egress -n meeting-automation --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl rollout status deployment/livekit-server deployment/livekit-egress -n meeting-automation
```

**Kritische Details:**
- **Service-Selector nach Helm prüfen**: Muss `app.kubernetes.io/name: livekit-server` + `app.kubernetes.io/instance: livekit-server` tragen (Staging-Lesson 9.6 — sonst 0 Endpoints!)
- **`LIVEKIT_URL=ws://livekit-server:7880` bleibt gültig**, weil `fullnameOverride: livekit-server` den Service-Namen beibehält
- **CI/CD**: `helm upgrade --install` verwenden (idempotent), Reihenfolge: NetworkPolicies VOR Helm, hostNetwork-Patch NACH Helm

### Phase 3 — Verifikation

| Check | Befehl | Erwartung |
|---|---|---|
| Pods Running | `kubectl get pods -l app.kubernetes.io/name=livekit-server` | 1/1 Running |
| **Service-Selector** | `kubectl get svc livekit-server -o jsonpath='{.spec.selector}'` | `app.kubernetes.io/name` + `instance` |
| **Endpoints** | `kubectl get endpoints livekit-server` | `169.58.83.32:7880,7881` |
| Backend-Connectivity | `kubectl exec deploy/backend -- python3 -c "connect('livekit-server',7880)"` | OK |
| Ingress | `curl https://meeting-automation.com/rtc` | kein 502 |
| E2E | Test-Meeting + Recording | Status `completed`, Transkription |

### Phase 4 — Nacharbeit

1. OLD-`app:`-Policies nach Stabilitätswoche entfernen (optional — additiv harmlos)
2. CI/CD commit + push → nächster Deploy automatisch Helm-konform
3. Recap-Dokument um Production-Migration ergänzen

---

## 5. Verifikation (Gates) — ERGEBNISSE (2026-08-08, alle bestanden)

| Gate | Phase | Kriterium | Ergebnis |
|---|---|---|---|
| **0** | 0 | `helm template` rendert gültige ConfigMap (`livekit:`-Schema, `keys: prod-...`) | ✅ Bestanden |
| **1** | 1 | Policies hinzugefügt, Endpoints unverändert | ✅ Bestanden |
| **2** | 2 | Pods 1/1, Service-Selector korrekt, Endpoints vorhanden | ✅ Bestanden |
| **3** | 2 | Backend → Service OK, Ingress kein 502 | ✅ Bestanden |
| **4** | 3 | E2E-Recording `completed` | ✅ Bestanden (2026-08-09, Staging-Volltest mit echtem Audio-Teilnehmer) |

### Durchgeführte Phasen (Live-Ergebnisse)

| Phase | Status | Details |
|---|---|---|
| **0.1** | ✅ | `livekit-server-values.yaml` auf `livekit:`-Schema, TURN aus, CPU 1000m (Commit `cb3877a0`) |
| **0.2** | ✅ | `network-policies.yaml`: OLD-Policies + Helm-Policies additiv (Commit `a7494a24`) |
| **1** | ✅ | Transition-Policies deployed: `livekit-policy-helm` + `livekit-egress-policy-helm` erstellt, Endpoints unverändert |
| **2** | ✅ | Helm-Migration: OLD-Deployments gelöscht, `helm install` aus vendored Charts, Service gelöscht (Helm-Import-Konflikt), hostNetwork-Patch, beide Pods Running |
| **3** | ✅ | 7 Gates: Pods 1/1, Selector Helm-Labels, Endpoints `169.58.83.32:7880,7881`, Backend OK, hostNetwork true, Server v1.9.0, Ingress 404 (erwartet) |
| **4a** | ✅ | `deploy-production.yml`: Chart-Name-Fix (`livekit/livekit-egress` → vendored `egress-1.8.4.tgz`), `helm upgrade --install`, Charts vendoriert unter `production/charts/` |
| **4b** | ✅ | Dieses Dokument aktualisiert |
| **4c** | ✅ | Staging-DiskPressure-Krise behoben + verifiziert (Details unten) |

### Wichtige Erkenntnisse aus der Migration

1. **Helm-Import-Konflikt**: Der 12-Tage-alte Service `livekit-server` (OLD-Labels, nicht Helm-managed) blockierte `helm install` → musste gelöscht werden, Helm erstellt ihn mit Helm-Labels neu
2. **`helm repo add livekit` versagte auf dem Server still** (durch `|| true` verschluckt) → Charts als Tarballs vendoriert unter `infrastructure/kubernetes/production/charts/`
3. **Falscher Chart-Name in CI/CD**: `livekit/livekit-egress` existiert NICHT (korrekt: `livekit/egress`) — wäre beim nächsten Deploy still fehlgeschlagen
4. **Service-Selector nach Helm**: korrekt `app.kubernetes.io/name` + `instance` → kein Staging-Endpoints-Bug in Production
5. **Egress pending-install-Lock**: abgebrochener SSH-Lauf hinterließ Lock → `helm uninstall` + frischer `helm upgrade --install`
6. **Staging-DiskPressure (2026-08-09)**: k3s-Node lief in Eviction-Schleife (imagefs-Schwelle 15% ≈ 27,5G von 183G). Root-Cause: Docker/moby-Store (38G) voll mit alten Build-Artefakten + Kubelet löscht bei DiskPressure ungenutzte k3s-Images → ImagePullBackOff-Welle (`pull QPS exceeded`). Fix: nur **verifiziert ungenutzte** Fix-Tags per `docker rmi` gelöscht (kein `docker system prune`, keine k3s-Images, Ollama unberührt), `DiskPressure=False`, Taint automatisch entfernt, 35+ Pods starteten wieder. **Lehre:** Disk-Puffer > 15% freihalten; alte Build-Tags nicht auf dem Produktions-Node ansammeln.
7. **E2E-Beweis (2026-08-09, Staging)**: Kompletter Pipeline-Test mit echtem Audio-Teilnehmer (`@livekit/rtc-node`, 440Hz-Ton, 20s): Meeting → Token → Recording-Start → Teilnehmer verbunden (wss) → Track publiziert → `EGRESS_ACTIVE` (kein „Start signal not received“ mehr) → Datei in MinIO (`515b661d..._livekit.ogg`, 335 KB) → `egress completed` → Recording `completed` → Transkription `completed` → PV `draft`. Der frühere `EGRESS_ABORTED`-Fehler trat **nicht** mehr auf.

### Phase 4c — Staging-Disk-Stabilisierung + E2E-Validierung (2026-08-09)

**Auslöser:** Während des E2E-Tests kollabierte Staging durch `DiskPressure=True` (183G-Disk, Eviction-Schwelle 27,5G frei). Evicted wurden u.a. `meeting-db-1` (PostgreSQL) → Login „Internal server error“ (`asyncpg Connection refused`), 42 Pending Pods.

**Root-Cause (verifiziert, nicht geraten):**
- Kubelet setzte `node.kubernetes.io/disk-pressure:NoSchedule`-Taint (06:11 UTC) → alle Pod-Starts blockiert
- Kubelet löscht bei DiskPressure ungenutzte Images (Image-GC) → k3s-containerd verlor referenzierte Images → Neustarts pullen von Docker Hub → `pull QPS exceeded` (Rate-Limit) → ImagePullBackOff-Welle
- Größte Speicherverbraucher: `/var/lib/containerd`/moby-Store 38G (alte `batnini/*`-Builds der Fix-Saga), Ollama-Modelle 11G, k3s-containerd 11G

**Fix (konservativ, schrittweise, mit Freigabe):**
1. Journal-Vacuum (`journalctl --vacuum-size=100M`) + alte Pod-Logs (>2 Tage) — AGENTS.md-sicher
2. Alte Completed/Failed Pod-Objekte gelöscht (keine Images)
3. Kubelet entfernte Taint automatisch nach DiskPressure=False
4. Nur **verifiziert ungenutzte** Fix-Tags per `docker rmi` gelöscht: `backend:3-fixes`, `backend:egress-audio-fix`, `frontend:15s-fix`, `3-fixes`, `60s-fix`, `ice-failover-fix`, `no-relay`, `timeout-30s`, `turn-relay`, `turn-relay-fix` (~7,3 GB). `latest` blieb. **Beweis der Nutzung:** k3s referenziert `batnini/*` ausschließlich über eigene SHA-Kopien im `k8s.io`-Namespace — kein Pod referenzierte die gelöschten Tags (per `kubectl get pods -A -o jsonpath` geprüft)

**Ergebnis:** `DiskPressure=False`, Taint entfernt, DB/Backend/Redis/MinIO wieder Running, Login HTTP 200, E2E-Pipeline vollständig erfolgreich.

**Noch offen (optional, mit Freigabe):** `backend:latest` (5,44 GB) + `frontend:latest` (119 MB) im Docker-Store — vom Cluster nicht referenziert (k3s hat eigene Kopien, andere SHA), aber als Quellen für neue Deploys nutzbar.

**✅ Inzwischen erledigt (2026-08-09, Abschluss):** `backend:latest` + `frontend:latest` per gezieltem `docker rmi` aus dem Docker-Store freigegeben (~3 GB, 94% → 93% Auslastung, 15G frei). Verifiziert: k3s hält eigene gepinnte Kopien (`io.cattle.k3s.pinned`), keine Pod-Referenz auf die Docker-Store-SHAs. Zusätzlich 28 evicted/error Pod-Artefakte der DiskPressure-Krise gelöscht. `DiskPressure=False`, 10/10 Deployments bereit, Login HTTP 200.

---

## 6. Rollback

```bash
helm rollback livekit-server livekit-egress -n meeting-automation
# oder: OLD-YAMLs wieder anwenden (falls Helm zurueckgebaut werden muss)
kubectl apply -f production/livekit-server-deployment.yaml -f production/livekit-egress-deployment.yaml
```

> **Hinweis nach Migration:** Helm ist jetzt die aktive Quelle. Rollback via `helm rollback` (Release-Revision). Die OLD-YAMLs sind nur noch Referenz.

---

## 7. Offene Punkte / Entscheidungen

| # | Frage | Status / Empfehlung |
|---|---|---|
| 1 | Wartungsfenster für Phase 2 (2–3 Min Downtime)? | ✅ **Durchgeführt** (2026-08-08) |
| 2 | TURN in Production deaktivieren (wie Staging)? | ✅ **Umgesetzt** (`turn.enabled: false` in Values) |
| 3 | `nodeSelector` für Production-Node? | ✅ **Ergänzt** (`contabo-prod`) |
| 4 | CPU 1000m (Staging-Wert)? | ✅ **Umgesetzt** (1000m) |
| 5 | E2E-Recording-Test | ✅ **Staging vollständig bestanden** (2026-08-09: Recording `completed`, Transkription, PV). Production: nur Smoke laut E2E-Strategie (Login/Meeting/Token/Status `idle`) — volle E2E in Production bewusst nicht ausgeführt |
| 6 | OLD-`app:`-Policies entfernen | Nach Stabilitätswoche (optional, additiv harmlos) |
| 7 | `backend:latest`/`frontend:latest` im Docker-Store (5,5 GB) | ✅ **Freigegeben** (2026-08-09, gezieltes `docker rmi`, ~3 GB — k3s-Kopien blieben unberührt) |
| 8 | Disk-Wachstum Staging überwachen | Empfehlung: > 15% frei halten; alte Build-Tags nicht auf dem Node ansammeln |

---

*Dieses Dokument dient als verbindlicher Migrationsplan. **Phasen 0–4c sind durchgeführt und verifiziert (2026-08-09).** Gate 4 (E2E-Recording) ist bestanden. Production läuft auf Helm wie Staging; Staging-DiskPressure-Krise behoben und dokumentiert.*
