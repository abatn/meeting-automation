# INCIDENT: E2E-Dev rot — MinIO-Pull verweigert (Quay/Docker-Hub)

**Datum:** 2026-09-24  
**Status:** Fix für E2E vorbereitet (Compose), Prod/Staging-Statefulsets bewusst unverändert  
**Betroffener Commit:** alle Commits nach 2026-09-22 (nicht code-bezogen)

## Symptom

- Job `build-and-test-dev` (Workflow „E2E Tests & Deployment Pipeline") failt bei jedem Run:
  - `minio-test Pulling`
  - `minio-test Error unauthorized: access to the requested resource is not authorized`
- Fehler tritt **vor** `pytest` bei `docker compose up` auf.
- Konsequenz: `deploy-staging-and-test` und `deploy-production` werden `skipped`.

## Root Cause (extern, belegt)

| Check | Ergebnis (2026-09-24) |
|-------|------------------------|
| `quay.io/v2/auth` scope `minio/minio:pull` | JWT `actions: []` (kein pull) |
| `quay.io/v2/auth` scope `minio/mc:pull` | JWT `actions: []` |
| `quay.io/v2/auth` Fremd-Namespaces (`prometheus/prometheus`, `coreos/etcd`, `argoproj/argocd`) | JWT `actions: ['pull']` → Quay funktioniert, nur `minio/*` gesperrt |
| `quay.io/v2/minio/minio/manifests/RELEASE.2024-12-18T13-15-44Z` | `401 UNAUTHORIZED` (identischer String wie im CI-Log) |
| Docker Hub `minio/minio` | Repo **404 (gelöscht)** — Compose-Kommentar vom 12.09. („removed from Docker Hub") war nur der erste Schritt |
| `dl.min.io/.../minio` (Binaries) | `410 Gone` |
| Compose `minio-test.image` | **identisch** in `540fcd1d` (grün 22.09.), `4fb1dfa0`, `c4e7f47f` |

**Zeitlinie CI (beweist „nicht Code"):**

| Datum | Run | Compose-Image | Pull |
|-------|-----|---------------|------|
| 22.09. 13:09 | `540fcd1` | quay pin | ✅ Pulled, 291 tests passed |
| 22.09. 19:03 | `4fb1dfa` | quay pin | ✅ Pulled, 291 tests passed |
| 24.09. 15:02 | `0ca2a14` | quay pin | ❌ unauthorized |
| 24.09. 19:21 | `c4e7f47` (= Inhalt 4fb1dfa0) | quay pin | ❌ unauthorized (identisch) |

## Impact

- **CI:** E2E-Dev immer rot; Staging-Automatik und Prod-Deploy-Pfad blockiert.
- **Laufzeit Staging/Prod:** aktuell OK (Node-Cache, `IfNotPresent`), **Neu-Pull würde genauso failen** — verstecktes Risiko bei Node-Tausch/Scaler.
- **Nicht betroffen:** Backend CI, Deploy Staging (Fast), laufender PV/Pipeline-Betrieb, lokale Entwicklung.

## Architektur-Abhängigkeit

- E2E-GitHub-Runner: **amd64**
- Staging-k3s: **arm64**
- Prod-k3s: **amd64**
- Lokales Cache-Image: nur arm64 — für CI unbrauchbar.

## Fix (Schritt 1 — nur E2E, kleinster Eingriff)

`docker-compose.e2e.yml` → `minio-test.image`:

- Neu: `elestio/minio@sha256:25348a257f1ece1b192f25f6cd9854618fa86422ac87b494b5d4e629c556d4bd`
- Verifiziert: echter MinIO-Server (`Entrypoint: docker-entrypoint.sh`, `Cmd: minio`, Historie `COPY /go/bin/minio*`, Version `RELEASE.2025-09-07T16-13-09Z`), Multi-Arch-Index (amd64+arm64), anonymer Pull `200`.
- **amd64-Binary im Index: `e_machine=0x3e` (EM_X86_64) ✓** → passt zum CI-Runner.
- **arm64-Variante kaputt:** Binary enthält ebenfalls `0x3e` (x86_64) statt `0xb7` (AArch64), Boot schlägt mit `Exec format error` fehl → **nicht für Staging verwenden**.
- Boot/S3-Laufbeweis amd64: lokal kein qemu → **E2E-Run ist der Freigabe-Beweis**.

## Follow-ups (offen, Freigabe nötig)

1. **Digest-Pin** bereits in Schritt 1 enthalten (Index-Digest, plattform-agnostisch).
2. **Staging-Statefulset** (`infrastructure/kubernetes/staging/minio-statefulset.yaml`): braucht ein **korrektes arm64-MinIO** — `elestio` fällt raus; Quay-Pin bleibt vorerst (läuft nur im Cache).
3. **Prod-Statefulset** (`.../production/minio-statefulset.yaml`): amd64 würde binary-seitig passen, aber Dritt-Mirror nach Prod = bewusste Risikoentscheidung + ggf. Hash-Abgleich gegen offizielles GitHub-Release (`github.com/minio/minio`).
4. Langfristig: eigener Multi-Arch-Mirror aus offiziellen Artefakten oder Quay-Login mit eigenen Credentials in der CI.

## Vertrauensfrage Dritt-Mirror (Elestio)

`elestio/minio` ist **nicht** von MinIO gebaut, sondern von Elestio (Hosting-Firma) nachgebaut. Build-Historie sieht sauber aus (`vcs-ref=da2e68be8d27b8fc647e4849048e9b39990407c6`, offizielles entrypoint, `mc`+`curl` enthalten), ist aber nicht signiert. Absicherung: Digest-Pin, Einsatz **nur in E2E** zuerst, kein Prod ohne explizite Freigabe.

## Beweis-Quellen

- CI: actions Run `36016496820` (0ca2a14), `36046953425` (c4e7f47), `35770537565` (4fb1dfa, grün), `35730966047` (540fcd1, grün)
- Registry-Checks: Bearer-Token `actions`-Claims, Manifest-Statuscodes, Hub-API 404
- Image-Config-Blob: Entrypoint/Cmd/Env/History via Registry-API
