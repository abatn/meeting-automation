# LiveKit Egress Skalierung — Gelöste Lösung (2026-09-11)

**Status:** ✅ ERFOLGREICH auf Staging getestet (2 Pods, beide verbunden)
**Namespace:** `meeting-automation-staging` (OCI, ARM64, Single-Node k3s v1.36.2)
**Datum:** 2026-09-11

---

## 1. Zusammenfassung

LiveKit Egress kann jetzt auf Staging horizontal skalieren (1→5 Pods) mit:

| Änderung | Vorher | Nachher |
|----------|--------|---------|
| **KEDA ScaledObject Target** | `livekit-egress` (existiert nicht → 28 Tage kaputt) | `livekit-egress-staging` ✅ |
| **Egress ws_url** | `ws://livekit-server-staging:7880` (Service DNS → DNAT blockiert) | `ws://10.0.0.191:7880` (Node-IP direkt) ✅ |
| **Egress hostNetwork** | `true` (Port-Konflikt bei 2 Pods) | `false` (kein Konflikt) ✅ |
| **NetworkPolicy** | nur `podSelector` | + `ipBlock: 10.0.0.191/32` Port 7880 ✅ |

**Ergebnis:** 2 Egress Pods laufen parallel, beide erreichen den LiveKit Server, KEDA ist READY/ACTIVE (erstmals nach 28 Tagen).

---

## 2. Die 3 Root Causes

### Root Cause 1: KEDA ScaledObject zeigte auf nicht existierendes Deployment (28 Tage unentdeckt)

**Beweis (vor dem Fix):**
```
$ kubectl get scaledobject -n meeting-automation-staging
NAME             SCALETARGETNAME       MIN   MAX   READY   ACTIVE
livekit-egress   livekit-egress        1     5     False   Unknown   ← ❌ 28 Tage kaputt!
```

```
$ kubectl get deploy -n meeting-automation-staging | grep livekit
livekit-egress-staging      ← realer Name (mit -staging Suffix)
livekit-server-staging
```

**Ursache:** `infrastructure/kubernetes/staging/keda-scaledobjects.yaml` (Zeile 58-75) hatte
`scaleTargetRef.name: livekit-egress` — aber das Deployment heißt `livekit-egress-staging`.
KEDA konnte nie skalieren: `READY=False, TARGETS=<unknown>` im HPA.

**Fix:**
```bash
kubectl patch scaledobject livekit-egress -n meeting-automation-staging \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/scaleTargetRef/name", "value": "livekit-egress-staging"}]'
```

**Ergebnis:** `READY=True, ACTIVE=True` (erstmals nach 28 Tagen).

### Root Cause 2: ws_url über Service DNS → DNAT zu hostNetwork-Server blockiert

**Beweis (vor dem Fix):**
```
$ kubectl exec deploy/livekit-egress-staging -- curl -s http://livekit-server-staging:7880
# Connection refused (exit code 7)
```

**Kette des Scheiterns:**
```
Egress (Pod-IP 10.42.0.214)
  → DNS: livekit-server-staging → ClusterIP 10.43.176.70
  → kube-proxy DNAT → Endpoint 10.0.0.191:7880 (Node-IP, weil Server hostNetwork: true)
  → CNI NetworkPolicy-Check: egress-Regel erlaubt podSelector app=livekit-server-staging
  → DNAT zur Node-IP matcht den podSelector NICHT korrekt
  → Connection refused
```

**Warum Backend funktioniert, Egress aber nicht:**
| Pod | Egress-NetworkPolicy | Server erreichbar |
|-----|---------------------|-------------------|
| Backend | KEINE (nur Ingress-Policy) | ✅ (darf alles senden) |
| Egress | JA (policyTypes: [Ingress, Egress]) | ❌ (Regel matcht DNAT-Ziel nicht) |

**Fix (offizieller Ansatz aus `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` §3.2):**
```yaml
egress:
  ws_url: ws://10.0.0.191:7880    # Node-IP direkt, NICHT Service DNS
```

Der Service wird komplett umgangen — keine DNAT, keine ClusterIP, direkte Verbindung zum Node.

**Deployment-Env geändert:**
```bash
kubectl -n meeting-automation-staging patch deployment livekit-egress-staging \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/env/3/value",
        "value": "ws://10.0.0.191:7880"}]'
# env Index 3 = LIVEKIT_WS_URL (nur mit vorheriger Verifikation der Env-Reihenfolge!)
```

### Root Cause 3: hostNetwork=true → Port-Konflikt bei Skalierung

**Beweis (vor dem Fix):**
```
$ kubectl scale deploy/livekit-egress-staging --replicas=2
$ kubectl get pods -l app=livekit-egress-staging
livekit-egress-staging-fff4c56d5-5wfb8   0/1   Pending
# Event: 0/1 nodes are available: 1 node(s) didn't have free ports
#        for the requested pod ports.
```

Ports, die kollidieren (Egress bindet auf Host):
- 7000 (Health)
- 7002 (Prometheus)
- 7980 (Template)

**Fix:**
```bash
kubectl -n meeting-automation-staging patch deployment livekit-egress-staging \
  --type='json' -p='[
    {"op": "remove", "path": "/spec/template/spec/hostNetwork"},
    {"op": "replace", "path": "/spec/template/spec/dnsPolicy", "value": "ClusterFirst"}
  ]'
```

### Begleitend: NetworkPolicy ipBlock erweitern

Ohne `ipBlock` würde die Egress-Egress-Policy (die NUR podSelectors erlaubt) die
Verbindung zur Node-IP blockieren:

```bash
kubectl patch networkpolicy livekit-egress-policy -n meeting-automation-staging \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/egress/2/to/-",
        "value": {"ipBlock": {"cidr": "10.0.0.191/32"}}}]'
# egress[2] = die Regel mit Port 7880 (mit vorheriger Verifikation der Regel-Reihenfolge!)
```

**Ergebnis der Regel:**
```json
{"ports":[{"port":7880,"protocol":"TCP"}],
 "to":[{"podSelector":{"matchLabels":{"app":"livekit-server-staging"}}},
       {"ipBlock":{"cidr":"10.0.0.191/32"}}]}
```

### Root Cause 4: minio-policy erlaubt Egress-Pods nicht als Ingress-Quelle

**Erst im 2. Testlauf entdeckt (19:53):** ICE/Media funktionierte, beide Egresses
nahmen auf — aber der S3-Upload scheiterte:
```
egress_failed: S3 upload failed: Put "http://minio-staging:9000/...":
  dial tcp 10.43.105.185:9000: connect: connection refused
```

**Diskriminierungstest:** Redis (ClusterIP) → exit 28 = verbunden ✅,
MinIO (Pod-IP UND ClusterIP) → exit 7 = refused ❌. Der Block liegt auf der
**MinIO-Ingress-Seite**: `minio-policy` (Ingress-Allow-Liste) enthält keine
Quelle für `livekit-egress-staging`, während `redis-policy` sie enthält.

**Warum das nie vorher auffiel:** Mit `hostNetwork: true` ist Egress-Traffic
Host-Traffic und **umgeht NetworkPolicies komplett** — MinIO akzeptierte die
Verbindungen trotz fehlender Regel. Erst als normaler Pod (Voraussetzung für
Skalierung) greift die Policy.

**Fix (Spiegelbild zum OnlyOffice→MinIO-Fix auf Production, 11.09. früh):**
```bash
kubectl patch networkpolicy minio-policy -n meeting-automation-staging \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/ingress/0/from/-",
        "value": {"podSelector": {"matchLabels": {"app": "livekit-egress-staging"}}}}]'
```
**Verifikation:** curl von Egress-Pod → MinIO health → `200 OK` ✅

---

## 3. Verifikation (nach allen Fixes)

### 3.1 Zwei Pods parallel

```
$ kubectl get pods -l app=livekit-egress-staging -o wide
NAME                                      READY   STATUS    IP            NODE
livekit-egress-staging-5f584c6c4c-l95xr   1/1     Running   10.42.0.217   instance-20260329-0846
livekit-egress-staging-5f584c6c4c-wswlx   1/1     Running   10.42.0.219   instance-20260329-0846
```

### 3.2 Connectivity beider Pods

| Test | Pod 1 | Pod 2 |
|------|-------|-------|
| `curl 10.0.0.191:7880` | ✅ OK | ✅ OK |
| Health `/health` | ✅ `{"CpuLoad":2}` | ✅ `{"CpuLoad":2}` |
| Redis-Verbindung | ✅ `connecting to redis` | ✅ `connecting to redis` |

### 3.3 KEDA-Zustand

```
$ kubectl get scaledobject livekit-egress -n meeting-automation-staging
NAME             SCALETARGETNAME          MIN   MAX   READY   ACTIVE
livekit-egress   livekit-egress-staging   1     5     True    True    ← ✅

$ kubectl get hpa keda-hpa-livekit-egress -n meeting-automation-staging
NAME                      REFERENCE                           TARGETS              MINPODS   MAXPODS   REPLICAS
keda-hpa-livekit-egress   Deployment/livekit-egress-staging   cpu: <unknown>/80%   1         5         2
```

---

## 4. Fehlgeschlagene Ansätze (dokumentiert zur Vermeidung)

| Ansatz | Ergebnis | Warum |
|--------|----------|-------|
| hostNetwork=false + Service-DNS ws_url | ❌ Connection refused | DNAT zu Node-IP matcht podSelector-Regel nicht |
| hostNetwork=true + 2 Pods | ❌ Pending (Port-Konflikt) | 7000/7002/7980 nur 1x pro Node |
| hostNetwork=true + Service-DNS (alter Stand) | ✅ funktioniert, aber 1 Pod max | Kein Scaling möglich |

**Schlüsselerkenntnis:** Die eigene Doku (`LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` §3.2)
hatte den korrekten Ansatz bereits definiert (`ws_url: ws://10.0.0.191:7880`), er war
aber nie in der tatsächlichen Deployment-Env umgesetzt worden.

---

## 5. Rollback-Verfahren

```bash
# 1. hostNetwork wiederherstellen
kubectl -n meeting-automation-staging patch deployment livekit-egress-staging \
  --type='json' -p='[
    {"op": "add", "path": "/spec/template/spec/hostNetwork", "value": true},
    {"op": "replace", "path": "/spec/template/spec/dnsPolicy", "value": "ClusterFirstWithHostNet"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/env/3/value",
     "value": "ws://livekit-server-staging:7880"}
  ]'

# 2. Auf 1 Pod skalieren
kubectl scale deploy/livekit-egress-staging -n meeting-automation-staging --replicas=1

# 3. NetworkPolicy ipBlock entfernen (optional, schadet nicht)
kubectl patch networkpolicy livekit-egress-policy -n meeting-automation-staging \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/egress/2/to",
        "value": [{"podSelector": {"matchLabels": {"app": "livekit-server-staging"}}}]}]'

# Backup aus der Simulation: /tmp/egress-staging-backup.yaml
```

---

## 6. Persistierung (erledigt 2026-09-11, Phase 1)

Die getestete Konfiguration ist in **beide Umgebungen** committet (vor jedem
Prod-Deploy — kein CI-Run kann sie mehr wegwerfen):

| Datei | Änderung | Env |
|-------|----------|-----|
| `infrastructure/kubernetes/staging/keda-scaledobjects.yaml` | `scaleTargetRef.name` → `livekit-egress-staging` (28-Tage-Bug) | Staging |
| `infrastructure/kubernetes/staging/livekit-egress-deployment.yaml` | hostNetwork=false, dnsPolicy ClusterFirst, ws_url → `ws://10.0.0.191:7880` | Staging |
| `infrastructure/kubernetes/staging/network-policies.yaml` | livekit-egress-policy: ipBlocks + Medien-Ports; minio-policy: Egress-Quelle | Staging |
| `infrastructure/kubernetes/production/livekit-egress-deployment.yaml` | hostNetwork=false, ws_url → `ws://169.58.83.32:7880`, CPU-Limit 1→2, Request 200m→500m | Prod |
| `infrastructure/kubernetes/production/keda-scaledobjects.yaml` | bereits korrekt (min1/max5) — der Live-Zustand MAX=1 war ein manueller Rollback-Patch und wird beim Re-Apply überschrieben | Prod |
| `infrastructure/kubernetes/production/network-policies.yaml` | livekit-egress-policy: ipBlocks (`169.58.83.32/32` + cni/flannel/docker0) + Medien-Ports; minio-policy: Egress-Quelle | Prod |

⚠️ **Hinweis:** Deployments sind kubectl-managed (nicht Helm). Die Manifeste
sind die Quelle — CI/CD-Deploy überschreibt kubectl-Patches nur, wenn die
Manifeste neu angewendet werden.

---

## 7. Production-Rollout (Plan, Phase 0 abgeschlossen)

**Phase 0 (read-only, 11.09.) — Ergebnisse:**

| Check | Befund |
|-------|--------|
| 0.1 Egress-Deployment | hostNetwork=true (post-Rollback), Resources 500m/2CPU/512Mi/2Gi, Image v1.9.0 |
| 0.2 Server-RTC | UDP 50000–60000, TCP 7881, TURN 3478, use_external_ip=true → ICE-Kandidaten: `169.58.83.32`, `10.42.0.0` (flannel.1), `10.42.0.1` (cni0), `172.17.0.1` (docker0) |
| 0.3 KEDA | READY=True, Target korrekt — aber **live MAX=1** (manueller Rollback-Patch; Git sagt max=5) |
| 0.4 Policies | egress-policy ohne Medien-Ports/ipBlocks; minio-policy ohne Egress-Quelle (OnlyOffice-Fix vom Vormittag vorhanden); redis-policy mit Egress ✅ |
| 0.5 **GATE** | Backend-Pod → `169.58.83.32:7880` → **200 OK** ✅ (Pod-Netzwerk → Node-IP funktioniert auf Prod) |

**Phase 2 — Canary-Reihenfolge (jeder Schritt reversibel):**

| # | Schritt | Verifikation vor dem nächsten |
|---|---------|------------------------------|
| 2.1 | minio-policy: Egress-Quelle patchen | unsafe — sofort möglich (hostNetwork-Pods umgehen sie ohnehin) |
| 2.2 | Egress-Policy: ipBlocks + Medien-Ports patchen | kubectl get networkpolicy — Struktur prüfen |
| 2.3 | Deployment: hostNetwork=false + ws_url Node-IP (Manifest anwenden, deckelt auch KEDA wieder auf max=5) | Pod Running; `curl 169.58.83.32:7880` aus dem Pod → OK |
| 2.4 | **Bei 1 Replica bleiben** → 1 Test-Meeting | ICE `connectionType: "udp"`, Stop → `EGRESS_COMPLETE`, Datei in MinIO |
| 2.5 | Erst dann auf 2 skalieren → 2 parallele Meetings | 2× EGRESS_COMPLETE, kein Port-Konflikt, KEDA READY=True |

**Restrisiko:** kube-router enforcing der ipBlock-Regeln (Staging-CNI ≠ kube-router).
Schlägt 2.3s curl-Test fehl → sofort Rollback (`/tmp`-Backups + hostNetwork zurück),
null Nutzer-Impact. Phase 2 startet nicht vor Commit der Phase-1-Manifeste.

---

## 8. Quellen

| Quelle | Relevanz |
|--------|----------|
| `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` §3.2, §5.7 | Offizieller ws_url-Ansatz (Node-IP) + Fehler-Checkliste "Egress skaliert nicht" |
| `docs/EGRESS_SCALING_PLAN_2026-08-06.md` | Original-Plan (hostNetwork entfernen), RollingUpdate-Strategie |
| `docs/AUTOSCALING_ARCHITECTURE_2026-08-14.md` | KEDA ScaledObject livekit-egress (min1/max5, CPU 80%) |
| `infrastructure/kubernetes/staging/keda-scaledobjects.yaml` | Enthielt den fehlerhaften Deployment-Namen |
| LiveKit Community #1899 | "Egress does NOT need hostNetwork" (bestätigt: es braucht nur erreichbaren Server) |
| LiveKit Doku (docs.livekit.io/transport/self-hosting/egress) | 4 CPU + 4 GB pro Egress-Instance, livekit_egress_available Metrik |

---

## 9. Offene Punkte

| # | Punkt | Status |
|---|-------|--------|
| 1 | Live-Test Staging: 2 parallele Recordings | ✅ 11.09. 19:24–19:32 — 2 Pods, ~8 Min, null Fehler; ICE/UDP ✅ |
| 2 | Git-Commit der Manifeste (Staging + Prod, Phase 1) | ✅ 11.09. erledigt |
| 3 | Production-Rollout (Phase 2, Canary 2.1–2.5) | ⏳ Phase 0 ✅, wartet auf Freigabe |
| 4 | Egress Resources auf LiveKit-Empfehlung (4 CPU / 4 GB) prüfen | ⏳ Aktuell 2 CPU / 2 Gi (getesteter Stand) |
| 5 | KEDA Custom Metric `livekit_egress_available` statt CPU (präziser) | ⏳ Optional |
| 6 | Stop-Button-Fix (Backend 404 → `already_stopped`; Frontend 404-Catch → `processing`) | ⏳ Separater Code-Fix, beide Umgebungen |
