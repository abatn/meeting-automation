# Plan: OnlyOffice "Download failed" in Staging beheben (Lösung 1 + PDF-Conv-Fix)

## Status
- **Plan-Mode**: Dies ist ein reiner Plan. Keine Edits/Commits/Pushes (alle verboten).
- **Basis**: Git-bewiesene Root-Cause-Analyse, keine Annahmen.

## Root Cause (100% bewiesen via Git + k8s-Inspektion)
1. **Ursprünglich funktionierend** (`commit 2ee88ab8`, 24.03.2026): `download_url` = `settings.ONLYOFFICE_BACKEND_URL` = **intern** (`http://backend:8000`). OnlyOffice-Server fetched intern.
2. **Bruch** (`commit 82af4b61`, 26.06.2026, letzter pv.py-Commit, live deployed als `:latest` rev 37): `download_url`/`callback_url` auf `public_base` (public HTTPS `https://staging.meeting-automation.com/...`) umgestellt.
3. **NetworkPolicy** (`commit 681abe61`, 23.06.2026): `onlyoffice-policy` erlaubt OnlyOffice-Pod **nur Egress zu backend:8000 (intern)**, KEIN Egress zum Ingress.
4. **Effekt**: OnlyOffice-Server fetcht `document.url` = public → muss durch Cluster-Netz zum Ingress → NP blockt → **"Download failed"**.
5. **Browser-Verhalten** (`frontend/src/components/meetings/OnlyOfficeEditor.tsx:79-80`): Browser lädt NUR die API-JS von `onlyOfficeUrl`, fetched `document.url` **nicht** direkt. OnlyOffice-Server fetched serverseitig. → Interne URL reicht.

## Entscheidung (User)
- **Lösung 1**: `document.url`/`callback_url` zurück zu **intern** (`settings.ONLYOFFICE_BACKEND_URL`).
- **PDF-Conv-Hardcode mitfixen**: Zeile 78 `http://backend:8000` → `settings.ONLYOFFICE_BACKEND_URL`.

## Warum Lösung 1 sicher ist
- `ONLYOFFICE_BACKEND_URL` (deployed, `backend-config.yaml:35`) = `http://backend.meeting-automation-staging.svc.cluster.local:8000` (Cluster-DNS, vom OnlyOffice-Pod auflösbar).
- OnlyOffice-Server fetcht intern → NP erlaubt backend:8000 Egress → **HTTP 200** (im Session-Test bereits bewiesen).
- Callback (`pv.py:486,496`): OnlyOffice gibt unsere `document.url` (intern) zurück → Backend fetched intern → OK.
- Kein NetworkPolicy-Touch nötig.

---

## Schritt-für-Schritt (nach Plan-Freigabe auszuführen)

### Schritt 1 — `backend/app/api/v1/pv.py` nur Editor-Config (Zeilen 400-411) anpassen
Revert meines `public_base`-Edits auf interne URL:

```python
# Zeilen 400-404 ersetzen durch:
download_url = f"{settings.ONLYOFFICE_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/download?file_key={file_key}&token={_sign_download(pv_id, file_key)}"
callback_url = f"{settings.ONLYOFFICE_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/callback?client_id={current_user.client_id}"
```
- `editorConfig.customization.onlyOfficeUrl` (Zeile 408): bleibt `public_base` (der Browser lädt API-JS von der public URL — das ist korrekt und nötig, damit `DocsAPI` geladen wird). **Nicht ändern.**
- `config["document"]["url"]` (Zeile 407): nutzt `download_url` → wird automatisch intern.

### Schritt 2 — `pv.py` PDF-Conv Hardcode fixen (Zeile 78)
```python
# Vorher (Zeile 78):
source_url = f"http://backend:8000/api/v1/pv/{pv_id}/onlyoffice/download?file_key={docx_key}&token={source_token}"
# Nachher:
source_url = f"{settings.ONLYOFFICE_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/download?file_key={docx_key}&token={source_token}"
```
- Begründung: `http://backend:8000` ist Docker-Service-Name, im k3s falsch (Cluster-DNS ist `backend.meeting-automation-staging.svc.cluster.local:8000`). `settings.ONLYOFFICE_BACKEND_URL` lädt den korrekten deployed Wert.

### Schritt 3 — Keine NetworkPolicy-Änderung
`onlyoffice-policy` bleibt unverändert (backend:8000 Egress bereits erlaubt). Keine `ipBlock`/CIDR-Hardcodierung.

### Schritt 4 — Build & Deploy (OHNE SKIP_SENTINEL)
1. Backend-Image neu bauen (KEIN `SKIP_SENTINEL`, damit Sentinel-Logik korrekt ist):
   ```bash
   cd /home/opc/meeting-automation/backend
   docker build -t docker.io/batnini/meeting-automation-backend:latest .
   ```
2. Image speichern nach `/home/opc` (NICHT `/tmp`):
   ```bash
   docker save docker.io/batnini/meeting-automation-backend:latest -o /home/opc/meeting-automation-backend-latest.tar
   ```
3. In k3s importieren:
   ```bash
   k3s ctr images import /home/opc/meeting-automation-backend-latest.tar
   ```
4. Rollout (k3s Image bereits `:latest` mit `IfNotPresent` → `imagePullPolicy` zwingt evtl. neuen Tag; falls `:latest` gecached, `kubectl rollout restart` reicht NICHT bei gleichem Tag. Sicherheitshalber Tag mit Timestamp versehen oder `kubectl set image` + restart):
   ```bash
   kubectl rollout restart deployment/backend -n meeting-automation-staging
   ```

### Schritt 5 — Verifikation (live, kein Annahmen)
1. **Server-fetch-Test** (wie im Session bewiesen):
   ```bash
   kubectl exec -it <onlyoffice-pod> -n meeting-automation-staging -- \
     wget -qO- "http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/pv/<test-pv>/onlyoffice/download?file_key=<key>&token=<token>" -O /dev/null -S 2>&1 | head
   ```
   Erwartung: `HTTP/1.1 200 OK`.
2. **Browser-Test**: `https://staging.meeting-automation.com/editor/<test-pv>?lang=en` → Kein "Download failed".
3. **OnlyOffice-Logs**: `kubectl logs <onlyoffice-pod> -n meeting-automation-staging` → kein `download error` / `ECONNREFUSED`.
4. **Editor-Save-Test**: Im Editor speichern → Callback (`pv.py:461`) muss `status 2/6` loggen + S3 `pv_exports/<pv>/edited_document.docx` aktualisieren.

### Schritt 6 — `.loop.md` Phase 182 finalisieren
Status: "gelöst + deployed" mit Dokumentation:
- Root Cause: `82af4b61` stellte `document.url` auf public, NP blockte Ingress-Egress.
- Fix: interne `ONLYOFFICE_BACKEND_URL` wiederhergestellt (wie `2ee88ab8`).
- PDF-Conv-Hardcode `backend:8000` → `ONLYOFFICE_BACKEND_URL`.

---

## Dateien (nur diese 2 werden geändert)
| Datei | Zeilen | Änderung |
|-------|--------|----------|
| `backend/app/api/v1/pv.py` | 400-404 | `download_url`/`callback_url` → `settings.ONLYOFFICE_BACKEND_URL` (intern) |
| `backend/app/api/v1/pv.py` | 78 | PDF-Conv `source_url` → `settings.ONLYOFFICE_BACKEND_URL` |

## Nicht geändert (bewusst)
- `infrastructure/kubernetes/staging/network-policies.yaml` (kein Egress-Change nötig)
- `frontend/src/components/meetings/OnlyOfficeEditor.tsx` (`onlyOfficeUrl` für API-JS bleibt public korrekt)
- `backend-config.yaml` (`ONLYOFFICE_BACKEND_URL` bereits korrekt gesetzt)

## Risiken
- **Callback `data.url` Mapping** (`pv.py:490-493`): Bei interner `document.url` fällt Callback-URL nicht in `localhost:8080`/`ONLYOFFICE_URL`-Branches → bleibt intern → Backend fetched intern. Sollte OK sein (OnlyOffice gibt originale `document.url` zurück). **Live in Schritt 5.4 verifizieren.**
- **`imagePullPolicy: IfNotPresent` + `:latest`**: k3s cached evtl. altes Image. Ggf. neues Tag verwenden statt `:latest`.
- **PDF-Conv benötigt Converter-Reachable**: `ONLYOFFICE_URL` = `http://onlyoffice-staging:80` (intern, korrekt im k3s). Converter-Egress bereits in NP erlaubt.

## Verbotene Aktionen (AGENTS.md / User)
- KEINE `git add` / `git commit` / `git push` / `git pull`.
- KEINE Image-Prunes (`docker system prune`, `k3s ctr images prune --all`).
- KEINE Hardcodierung (IP/CIDR/Domain) — nur Settings-Variablen + Label-basierte NP.
- KEINE Löschung von Fehler-Reporting (Löschen ist verboten).
