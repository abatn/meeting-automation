# OnlyOffice "Download failed" Fix — Cache Regex Bug

**Datum:** 2026-08-04
**Status:** Behoben
**Commit:** ConfigMap `onlyoffice-custom-config` — ds-docservice.conf Regex-Fix

---

## Symptom

OnlyOffice Editor zeigt **"Download failed"** wenn ein Document geöffnet wird. Das Document (z.B. PV als .docx) wird konvertiert aber nicht geladen.

### nginx Error Log

```
2026/08/04 23:00:47 [error] *41 open() "/var/lib/onlyoffice/documentserver/App_Data/cache/files/data/1884358d-.../Editor.bin/Editor.bin" failed (20: Not a directory)
```

**Fehler (20: Not a directory)** bedeutet: nginx versucht `Editor.bin/Editor.bin` zu öffnen, aber `Editor.bin` ist eine **Datei**, kein Verzeichnis.

---

## Root Cause

### Das Problem

Die Custom `ds-docservice.conf` ConfigMap hatte die **falsche Regex-Pattern** für den `/cache/files` nginx Location-Block.

**Vorher (kaputt):**

```nginx
location ~* ^(\/cache\/files.*)$ {
  alias /var/lib/onlyoffice/documentserver/App_Data$1;
```

**Nachher (fix — gemäß offiziellem OnlyOffice Template):**

```nginx
location ~* ^(\/cache\/files.*)(\/.*) {
  alias /var/lib/onlyoffice/documentserver/App_Data$1;
```

### Warum das schiefging

OnlyOffice nutzt eine URL-Struktur für den Cache:

```
/cache/files/data/{document-key}/Editor.bin/Editor.bin?md5=...&expires=...
```

Der Converter (x2t) speichert die konvertierte Datei als **flache Datei**:

```
cache/files/data/{document-key}/Editor.bin    (Datei, 152KB)
```

Die URL `Editor.bin/Editor.bin` bedeutet:
- `Editor.bin` (erster Teil) = der Pfad zur flachen Datei
- `Editor.bin` (zweiter Teil) = der Dateiname (wird in der URL für `filename=` Parameter genutzt)

### Regex-Verhalten

Mit der falschen Regex `^(\/cache\/files.*)$` (eine Capture-Gruppe):

```python
# URL: /cache/files/data/1884358d-.../Editor.bin/Editor.bin
$1 = /cache/files/data/1884358d-.../Editor.bin/Editor.bin  # ALLES
# → Alias resolved auf: App_Data/.../Editor.bin/Editor.bin
# → Datei nicht gefunden: (20: Not a directory)
```

Mit der korrekten Regex `^(\/cache\/files.*)(\/.*)` (zwei Capture-Gruppen):

```python
# URL: /cache/files/data/1884358d-.../Editor.bin/Editor.bin
$1 = /cache/files/data/1884358d-.../Editor.bin  # Pfad bis letzter /
$2 = /Editor.bin                                 # Dateiname
# → Alias resolved auf: App_Data/.../Editor.bin
# → Datei gefunden ✅
```

Der `$` Anchor am Ende der alten Regex war das Hauptproblem. Er zwang die Regex, die gesamte URI in `$1` zu erfassen. Die offizielle OnlyOffice Regex hat keinen `$` Anchor und zwei Capture-Gruppen, wodurch der Pfad korrekt getrennt wird.

---

## Quellen

| Datei | Beschreibung |
|-------|-------------|
| Offizielles Template | [ds-docservice.conf.m4](https://github.com/ONLYOFFICE/document-server-package/blob/master/common/documentserver/nginx/includes/ds-docservice.conf.m4) |
| ConfigMap (Git) | `infrastructure/kubernetes/staging/onlyoffice-custom-config.yaml` |
| nginx Config im Pod | `/etc/onlyoffice/documentserver/nginx/includes/ds-docservice.conf` |
| Cache-Verzeichnis | `/var/lib/onlyoffice/documentserver/App_Data/cache/files/data/` |

---

## Chronologie

1. OnlyOffice Pod zeigt "Download failed" beim Öffnen von Documents
2. nginx Error Log zeigt `(20: Not a directory)` für `Editor.bin/Editor.bin`
3. Cache-Struktur analysiert: Converter erstellt flache `Editor.bin` Datei (152KB)
4. Nur die zweite `.bin` fehlt als separater Pfad
5. **Vergleich mit offiziellem Template** zeigt: Unterschiedliche Regex-Gruppen
6. Test bestätigt: Zweite Capture-Gruppe korrigiert den Alias-Pfad
7. ConfigMap gefixt, Pod neu gestartet
8. Document-Öffnen funktioniert ✅

---

## Was wurde NICHT durch dieses Problem verursacht

Folgende Hypothesen wurden im Laufe der Investigation geprüft und als **falsch** verworfen:

| Hypothese | Warum nicht |
|-----------|-------------|
| `document.url` public vs intern | Phase 182 fix (interner URL) IS deployed ✅ |
| Mixed Content / HTTP vs HTTPS | nginx-ingress handled `X-Forwarded-Proto` |
| `onlyoffice-proxy-headers` ConfigMap fehlte | Working commit `469a7b0a` hatte sie auch nicht |
| `SERVER_NAME` env Var fehlte | Hinzugefügt, getestet — kein Effekt |
| `ALLOW_PRIVATE_IP_ADDRESS` fehlte | War im Deployment, nur nicht im Pod sichtbar |
| Cache-Korruption | Cache löschen + Neustart reproduziert gleichen Fehler |
| NetworkPolicy | OnlyOffice→Backend Fetch funktioniert (HTTP 200) |
| Image-Version `latest` vs `9.4.0` | Beide haben denselben Bug |
| ARM64-Architektur | Kein ARM64-spezifisches Problem |

---

## Änderungen

### Datei: `infrastructure/kubernetes/staging/onlyoffice-custom-config.yaml`

```diff
-    location ~* ^(\/cache\/files.*)$ {
+    location ~* ^(\/cache\/files.*)(\/.*) {
```

**Eine Zeile. Ein Regex-Gruppen. Null其他的 Änderungen.**

### Cluster

- ConfigMap `onlyoffice-custom-config` angewendet via `kubectl apply`
- Deployment `onlyoffice-staging` neu gestartet via `kubectl rollout restart`
- Alter Cache geleert: `rm -rf /var/lib/onlyoffice/documentserver/App_Data/cache/files/data/*`

---

## Lektion gelernt

> **Wenn OnlyOffice Docs von nginx-Konfiguration abweichen, IMMER das offizielle Template auf GitHub vergleichen.**

Die Custom `ds-docservice.conf` wurde früher manuell erstellt und wich in der Regex vom offiziellen Template ab. Dieser kleine Unterschied (eine vs. zwei Capture-Gruppen) verursachte einen kryptischen `(20: Not a directory)` Fehler, der wie ein Converter-Bug aussah, aber ein Config-Bug war.

---

## Zusammenhang mit OnlyOffice GitHub Issues

| Issue | Ähnlichkeit | Relevanz |
|-------|------------|----------|
| [#1020](https://github.com/ONLYOFFICE/DocumentServer/issues/1020) | Bestätigt: `Editor.bin/Editor.bin` ist das NORMALE URL-Muster | ✅ Hoch |
| [#58](https://github.com/ONLYOFFICE/Docker-DocumentServer/issues/58) | Permission denied (13), nicht Not a directory (20) | ❌ |
| [#424](https://github.com/ONLYOFFICE/Docker-DocumentServer/issues/424) | NAS Volume-Mount Problem | ❌ |
| [#938](https://github.com/ONLYOFFICE/DocumentServer/issues/938) | `secretString` mismatch → 403 | ❌ |
| [#1833](https://github.com/ONLYOFFICE/DocumentServer/issues/1833) | Virtual path proxy URL mismatch | ❌ |
| [#1290](https://github.com/ONLYOFFICE/DocumentServer/issues/1290) | Bestätigt: `Editor.bin/Editor.bin` ist normal | ✅ Hoch |
| [#3625](https://github.com/ONLYOFFICE/DocumentServer/issues/3625) | Security: URL-Expiration zu lang | ⚠️ Separates Thema |
