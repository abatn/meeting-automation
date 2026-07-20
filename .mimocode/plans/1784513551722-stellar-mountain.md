# Plan: OnlyOffice Fix — 403 Forbidden nach Mixed-Content-Fix

## Status
- Mixed-Content-Fix funktioniert ✅ (HTTPS-URLs werden generiert)
- Neuer Fehler: 403 Forbidden auf `/cache/files/.../Editor.bin`

## Aktueller Stand
- "Download failed" (Mixed Content) ist **GELÖST** durch `storage.externalHost` im laufenden Pod ✅
- 403-Fehler ist ein **Regression durch meine ConfigMap-Erstellung** — nicht das ursprüngliche Problem
- ConfigMap hat falsche Werte (`storage.fs.secretString` mismatch mit `SECURE_LINK_SECRET`)

## Nächster Schritt
Die funktionierende Config aus dem laufenden Pod (7f9c7c7fb5-nmkxt) EXAKT in die ConfigMap übernehmen:
1. `local.json` aus dem Pod auslesen (nicht raten)
2. ConfigMap mit exakten Werten neu erstellen
3. Pod neu starten und testen

## Verifikation
1. `kubectl apply -f onlyoffice-deployment.yaml`
2. Pod neu starten
3. Editor testen → 403 sollte weg sein
4. F12 → Console → Kein Mixed Content + Kein 403

## Quelle
- Offizielle OnlyOffice Docker-Doku: `SECURE_LINK_SECRET` = "Defines secret for the nginx config directive secure_link_md5. Defaults to random string."
- Nginx-Config (`ds-docservice.conf`): `secure_link_md5 "$secure_link_expires$uri$secure_link_secret";`
- DocService-Config (`local.json`): `storage.fs.secretString: "ijFyRtf6wcGYWNCHT28W"`
- Wert MUSS übereinstimmen, sonst 403
