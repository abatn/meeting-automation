# Production LiveKit Helm Migration — Plan & Staging-Abgleich (2026-08-08)

**Erstellt:** 2026-08-08
**Ziel:** Production (`meeting-automation` / Contabo `169.58.83.32`) 100% auf Helm wie Staging bringen — ohne Ausfall.
**Ausgangslage:** Production läuft seit 12 Tagen stabil mit **direkten YAML-Deployments** (OLD-Labels `app:`). Die Repo-Dateien für Helm-Values existieren, sind aber **nicht chart-konform** und würden bei einem CI/CD-Deploy Production brechen.

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
| `nameOverride` | `livekit-server-staging` | `livekit-server` | ✅ (Namensunterschied ok) | — |
| `fullnameOverride` | `livekit-server-staging` | `livekit-server` | ✅ (Namensunterschied ok) | — |
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
| `resources.limits.cpu` | `1000m` | ❌ `2000m` | **NEIN** | `1000m` |
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
| `ws_url` | `ws://livekit-server-staging:7880` | `ws://livekit-server:7880` | ✅ (Env) | — |
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
| `livekit-policy` podSelector | `app.kubernetes.io/name: livekit-server-staging` | ❌ `app.kubernetes.io/name: livekit-server` (nur Helm-Label) | ⚠️ | **Transition:** OLD-Policy `app: livekit-server` BEHALTEN + NEUE `livekit-policy-helm` HINZUFÜGEN (podSelector kann kein OR) |
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

**Wert-Abweichung bei gemeinsamen Keys:** `resources.limits.cpu` = staging `1000m` vs. prod `2000m` ❌

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
3. **`turn.enabled: true` ohne TLS** → bekannter `403 CreatePermission` (Staging-Lesson #5)
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

## 5. Verifikation (Gates)

| Gate | Phase | Kriterium |
|---|---|---|
| **0** | 0 | `helm template` rendert gültige ConfigMap (`livekit:`-Schema, `keys: prod-...`) |
| **1** | 1 | Policies hinzugefügt, Endpoints unverändert |
| **2** | 2 | Pods 1/1, Service-Selector korrekt, Endpoints vorhanden |
| **3** | 2 | Backend → Service OK, Ingress kein 502 |
| **4** | 3 | E2E-Recording `completed` |

---

## 6. Rollback

```bash
helm rollback livekit-server livekit-egress -n meeting-automation
# oder: OLD-YAMLs wieder anwenden
kubectl apply -f production/livekit-server-deployment.yaml -f production/livekit-egress-deployment.yaml
```

---

## 7. Offene Punkte / Entscheidungen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Wartungsfenster für Phase 2 (2–3 Min Downtime)? | Außerhalb Geschäftszeiten |
| 2 | TURN in Production deaktivieren (wie Staging)? | **Ja** — ohne TLS-Cert ist TURN ein 403-Risiko |
| 3 | `nodeSelector` für Production-Node? | Production ist single-node → optional, aber für 100%-Parität ergänzen |
| 4 | CPU 1000m (Staging-Wert)? | **Ja** — Nutzung ~6m, 2000m überdimensioniert |

---

*Dieses Dokument dient als verbindlicher Migrationsplan. Keine Änderung am Cluster ohne Freigabe und ohne Gate-Verifikation.*
