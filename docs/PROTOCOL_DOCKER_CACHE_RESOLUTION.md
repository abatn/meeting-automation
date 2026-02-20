# PROTOKOLL: LÖSUNG VON DOCKER-CACHE PROBLEMEN (Backend Fix)

Datum: 20.02.2026
Status: Abgeschlossen

## 🎯 PROBLEM
Trotz Aktualisierung der `requirements.txt` meldete der Backend-Container weiterhin einen `ImportError: email-validator`.

## 🔍 URSACHENANALYSE
Warum wurde die neue Dependency nicht übernommen?

1.  **Docker Layer Caching**: Docker cached den `pip install` Layer. Wenn sich der Befehl im Dockerfile (`RUN pip install ...`) nicht ändert, nutzt Docker oft den Cache der alten Installation, anstatt die `requirements.txt` neu einzulesen.
2.  **Image-Inkonsistenz**: Ein einfacher Neustart (`docker-compose up`) erkennt Änderungen in Quelldateien, löst aber nicht zwingend einen neuen Build des Images aus, wenn das Image bereits lokal existiert.
3.  **Volume-Überlagerung**: In Entwicklungs-Umgebungen können gemountete Volumes (`./backend:/app`) zwar Code synchronisieren, aber keine Bibliotheken, die im Image-internen `/usr/local/lib/python3.11/site-packages` installiert sind.

## 🔧 LÖSUNG
- Einsatz von `docker-compose build --no-cache backend`, um Docker zu zwingen, alle Layer (einschließlich der Paketinstallation) von Grund auf neu zu erstellen.
- Bereitstellung des Scripts `scripts/fix-backend-cache.sh` für eine saubere Neuinstallation.

## 📝 DURCHGEFÜHRTE SCHRITTE
1.  Identifikation des Cache-Problems.
2.  Erstellung eines Force-Build Scripts.
3.  Verifizierung der Installation mittels `pip show` im laufenden Container.

## 📊 ERGEBNIS
Die Dependency ist nun im Image-Layer fest verankert und der Startup-Fehler behoben.
