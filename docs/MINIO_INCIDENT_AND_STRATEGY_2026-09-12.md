# MinIO — Incident, Fix und Zukunftsplanung (2026-09-12)

## 1. Incident: MinIO-Images aus Docker Hub entfernt

**Datum des ersten Auftretens:** 2026-09-11 (CI-Run #34649905042, ~21:32 UTC)

### Was passierte
- MinIO hat **alle Images aus Docker Hub entfernt** (`minio/minio` und `library/minio` → 404, live verifiziert via Docker Hub API).
- MinIO's offizielle Registry ist jetzt **quay.io** (`quay.io/minio/minio`).
- CI-Lauf #34649905042 brach im Job `build-and-test-dev` ab, **bevor ein einziger Test lief**:
  ```
  pull access denied for minio/minio, repository does not exist or may require 'docker login'
  ```
- Betroffen: `docker-compose.e2e.yml` (CI), `docker-compose.yml` (Dev), `docker-compose.prod.yml`, `infrastructure/docker/docker-compose.yml`.

### Beweiskette (wichtig für spätere Analyse-Muster)
| Beweis | Ergebnis |
|---|---|
| Letzter grüner Run (#34585440229, 09:41) vs. roter Run (#34649905042, 21:32) | **Identische Compose-Datei** (`git diff` leer) |
| Letzter Commit auf `docker-compose.e2e.yml` | `9abadee4`, 2026-07-11 — 2 Monate alt |
| Registry-Check (live) | `minio/minio` → 404, `library/minio` → 404, Tag-Liste → `object not found` |
| Unsere 4 Commits (0082e096..0dfa485f) | Nur K8s-YAML + Docs — **unschuldig** |

**Muster für die Zukunft:** „Vorher grün, nachher rot, Git unverändert" → immer zuerst externe Abhängigkeiten prüfen (Registry, API, CDN), bevor im eigenen Code gesucht wird.

## 2. Angewandter Fix (Commit `020e2e95`)

- **Neue Image-Quelle:** `quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z`
  - Exakt die Version, die **bereits in Prod UND Staging läuft** (beide StatefulSets hatten diesen Pin)
  - Offizielle MinIO-Registry (quay.io) — kein Mirror nötig
- **7 Dateien geändert:**
  - `docker-compose.yml` (Dev)
  - `docker-compose.e2e.yml` (CI)
  - `docker-compose.prod.yml`
  - `infrastructure/docker/docker-compose.yml`
  - `infrastructure/kubernetes/minio-statefulset.yaml`
  - `infrastructure/kubernetes/production/minio-statefulset.yaml`
  - `infrastructure/kubernetes/staging/minio-statefulset.yaml`
- **Verifiziert vor Commit:** `docker pull` ✅ + `minio --version` → `RELEASE.2024-12-18T13-15-44Z` ✅
- **Cluster wurden NICHT angefasst** — Prod/Staging laufen weiter auf dem lokalen Cache. Beim nächsten `kubectl apply` der StatefulSets wird quay.io verwendet (gleicher Tag → kein Rollout-Content-Change erwartet, aber Image-Reference-Änderung löst einen Pod-Restart aus — bei Migration einplanen!).

### ⚠️ Offene Folgeaufgabe
Die StatefulSets in Prod/Staging laufen noch mit `minio/minio:RELEASE...` (Docker-Hub-Referenz). Da der Tag gecacht ist, funktioniert der Betrieb — **aber ein Node-Failover mit ImagePullPolicy-Neuzug würde fehlschlagen**. Beim nächsten geplanten Wartungsfenster die Git-Manifeste anwenden (quay.io-Referenz), damit die Cluster-Definitionen wiederherstellbar sind.

## 3. Strategisches Risiko: MinIO im Wartungsmodus

> **Hinweis:** Die folgenden Punkte stammen aus einer externen Analyse (User-Eingabe vom 2026-09-12). Vor Entscheidungen sind die CVE-Nummern und Claims eigenständig zu verifizieren.

### Kernproblem
- Das Open-Source-Projekt MinIO ist offiziell in den **Wartungsmodus** übergegangen:
  - Keine neuen Features, keine Pull-Requests mehr akzeptiert
  - **Kritische Sicherheitslücken werden nicht mehr aktiv gepatcht** (Beispiel-Claim: CVE-2026-39414, DoS via S3 Select/CSV — zu verifizieren)
- Konsequenz: Sicherheits- und Wartungsrisiko trägt der Betreiber selbst.
- Enterprise-Edition: sechsstellige Jahreskosten (Claim — verifizieren).

### Relevanz für Meeting Automation
- Wir speichern **Meeting-Aufnahmen und PV-Dokumente** (ISO 27001-relevant) in MinIO (S3-API).
- Ein ungepatchter CVE im S3-Stack betrifft direkt unsere Compliance-Position.
- Deployment: StatefulSet auf Single-Node-k3s (Prod) + Staging — kein verteilter Modus, relativ einfacher Austausch.

## 4. Alternativen (aus externer Analyse — vor Evaluation verifizieren)

| Alternative | Status | Stärken | Schwächen | Bewertung für uns |
|---|---|---|---|---|
| **MinIO (Community)** | Wartungsmodus | Läuft stabil, S3-API, gecachte Images | Keine Security-Patches, Docker-Hub-Entfernung zeigt also Richtung | ⚠️ Kurzfristig OK, mittel-/langfristig Risiko |
| **MinIO Enterprise** | Kommerziell | Patches, Support | Sechsstellige Jahreskosten (Claim) | Nur wenn Compliance es erzwingt |
| **RustFS** | Alpha | Rust, Apache 2.0, schnell bei kleinen Objekten | Nicht produktionsreif, verteilter Modus/KMS in Erprobung, CVE-2025-68926 (CVSS 9.8, behoben) zeigt Jugend | ❌ Aktuell nein, beobachten |
| **SeaweedFS** | Etabliert | S3-kompatibel, stark bei vielen kleinen Dateien | Komplexer Betrieb, braucht Speicher-Know-how | 🤔 Kandidat, Evaluierung nötig |
| **Ceph (RGW)** | Ausgereift | Enterprise-reif, S3 via RADOS Gateway, hohe Ausfallsicherheit | Sehr komplex, Overkill für einfachen S3-Speicher | 🤔 Nur bei Mehr-Node-Cluster |
| **Cloud-S3 (OCI/Contabo-freundlich)** | Kommerziell | Kein eigener Betrieb, Patches vom Anbieter | Daten liegen außerhalb (ISO 27001-Klärung nötig), Kosten | 🤔 Falls lokale S3-Pflicht fällt |

## 5. Entscheidungsvorlage für die Zukunft

### Triggert für eine Migration ( beliebige Bedingung erfüllt )
1. Ein **realer CVE** in MinIO Community wird öffentlich ausgenutzt und nicht gepatcht
2. Quay.io-Images werden ebenfalls **eingeschränkt oder entfernt** (Registry-Risiko wandert mit)
3. Compliance-Audit (ISO 27001) fordert **aktive Security-Pflicht** für Storage-Komponenten
4. MinIO Enterprise-Angebot wird für uns relevant (Kostenfreigabe vorhanden)

### Kurzfristig (Q3/Q4 2026) — keine Migration
- ✅ quay.io-Pin überall angewendet (Commit `020e2e95`)
- ⏳ Cluster-StatefulSets auf quay.io-Referenz heben (nächstes Wartungsfenster, siehe §2)
- ⏳ ImagePullPolicy + Node-Failover-Szenario testen (Staging)
- ⏳ CVE-Lage quartalsweise prüfen (MinIO-GitHub + NVD)

### Mittelfristig (2027) — Evaluierung
- **SeaweedFS** in Staging parallel testen (gleiche S3-Buckets-API, LiveKit-Egress + OnlyOffice + Celery-Pipeline sind die Kunden der S3-API)
- Migrationsaufwand schätzen: Datenmigration via `mc mirror` / rclone, App-Umstellung nur über ENV (S3_ENDPOINT bleibt)
- **Wenn 2. Node für Prod kommt (Egress-Skalierung):** Ceph-RGW mitbewerten — dann existiert ohnehin Multi-Node

### Architektur-Notiz (macht jede Migration billig)
Alle S3-Konsumenten (LiveKit-Egress, OnlyOffice, Backend, Celery) nutzen bereits **S3_ENDPOINT aus ENV** — keine Hardcodes. Eine Migration sollte daher nur:
1. Neuen Storage deployen
2. `mc mirror` für Daten
3. ENV umstellen + Rollout
4. Alten Storage entfernen

## 6. Quellen
- CI-Run #34649905042 (Fehlerlog: `pull access denied for minio/minio`)
- Live-Registry-Checks 2026-09-12: hub.docker.com API → 404; quay.io Manifest → 200; `docker pull` + `minio --version` → OK
- Commit `020e2e95` (7 Dateien, quay.io-Pin)
- Externe Analyse zum MinIO-Wartungsmodus + Alternativen (User-Eingabe 2026-09-12 — **unverifiziert**, vor Entscheidungen prüfen)
