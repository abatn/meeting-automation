# Prompt: Chrome-Startup-Debug auf Production

## KONTEXT

LiveKit Egress auf Production (AMD64) schlägt bei JEDEM Recording mit dem Fehler `template page load failed: websocket url timeout reached` fehl. Auf Staging (ARM64) funktioniert es.

**Bisherige Analyse:**
- CPU-Fix (1→2) hat NICHT geholfen — kein "not enough cpu" Error mehr, aber Chrome startet trotzdem nicht
- Chrome-Prozesse werden SOFORT zu Zombies nach Launch
- Auf ARM64: Chrome startet in 14s → Erfolg
- Auf AMD64: Chrome startet nicht innerhalb 20s → Timeout
- Beide haben: hostNetwork=true, /dev/shm=64MB, Chrome 125.0.6422.60

## AUFGABE

Finde heraus WARUM Chrome auf Production (AMD64) nicht startet. Prüfe jeden dieser Punkte:

### 1. Chrome DevTools WebSocket Port

```bash
# Prüfe ob Chrome den Debug-Port öffnen kann
# Chrome sollte --remote-debugging-port=0 nutzen
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c 'echo "Port test:"; timeout 5 sh -c "while true; do ss -tlnp | grep chrome; sleep 0.5; done" 2>&1 || echo "No chrome port found"'
```

**Erwartung:** Chrome öffnet einen Random-Port auf localhost
**Problem:** Bei `hostNetwork: true` könnte ein Port-Konflikt vorliegen

### 2. Chrome stderr/stdout Analyse

```bash
# Starte Chrome manuell mit Debug-Output
kubectl exec -it deployment/livekit-egress -n meeting-automation -- sh -c '
  export DISPLAY=:99999
  Xvfb :99999 -screen 0 1280x720x24 &
  sleep 1
  timeout 25 /opt/google/chrome/chrome \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --remote-debugging-port=0 \
    --remote-debugging-address=127.0.0.1 \
    http://localhost:7980 2>&1 | head -50
'
```

**Erwartung:** Chrome gibt `DevTools listening on ws://127.0.0.1:XXXX` aus
**Problem:** Wenn Chrome die URL nicht ausgibt → chromedp Timeout

### 3. Chrome Flags prüfen

```bash
# Prüfe welche Chrome-Flags Egress setzt
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c '
  cat /proc/$(pgrep -f "chrome" | head -1)/cmdline 2>/dev/null | tr "\0" "\n" | head -30
'
```

**Erwartung:** `--no-sandbox`, `--disable-gpu`, `--remote-debugging-port=0`
**Problem:** Fehlende Flags könnten Chrome-Start verhindern

### 4. Shared Memory prüfen

```bash
# Chrome braucht /dev/shm für Shared Memory
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c '
  echo "=== /dev/shm ==="
  df -h /dev/shm
  echo "=== /dev/shm usage ==="
  ls -la /dev/shm/
  echo "=== Chrome memory usage ==="
  cat /proc/meminfo | grep -E "Shmem|MemAvail"
'
```

**Erwartung:** /dev/shm mindestens 128MB, Chrome kann allozieren
**Problem:** 64MB könnte zu wenig sein für Chrome + GStreamer

### 5. Display/Xvfb prüfen

```bash
# Prüfe ob Xvfb korrekt läuft
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c '
  echo "=== DISPLAY ==="
  echo $DISPLAY
  echo "=== Xvfb process ==="
  ps aux | grep -E "Xvfb|xvfb" | grep -v grep
  echo "=== X display test ==="
  xdpyinfo -display $DISPLAY 2>&1 | head -10
'
```

**Erwartung:** DISPLAY gesetzt, Xvfb läuft, xdpyinfo zeigt Bildschirm
**Problem:** Wenn Display nicht funktioniert → Chrome kann nicht rendern

### 6. Chrome-Sandbox prüfen

```bash
# Chrome braucht evtl. spezielle Sandbox-Settings
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c '
  echo "=== User ==="
  whoami
  id
  echo "=== Chrome sandbox test ==="
  timeout 10 /opt/google/chrome/chrome --version 2>&1
  echo "=== Chrome help ==="
  timeout 5 /opt/google/chrome/chrome --help 2>&1 | grep -i sandbox
'
```

**Erwartung:** Chrome läuft als `egress` User, Sandbox-Settings korrekt
**Problem:** Fehlende Sandbox-Berechtigungen

### 7. Library-Dependencies prüfen

```bash
# Prüfe ob alle Chrome-Libraries vorhanden sind
kubectl exec deployment/livekit-egress -n meeting-automation -- sh -c '
  echo "=== Missing libraries ==="
  ldd /opt/google/chrome/chrome 2>&1 | grep "not found"
  echo "=== Chrome dependencies ==="
  ldd /opt/google/chrome/chrome 2>&1 | wc -l
'
```

**Erwartung:** 0 "not found" Meldungen
**Problem:** Fehlende Library → Chrome crasht

### 8. Egress Helm Chart Chrome-Config prüfen

```bash
# Prüfe ob Helm Chart Chrome-Flags korrekt setzt
kubectl get configmap livekit-egress -n meeting-automation -o yaml 2>&1 | grep -A5 -B5 "sandbox\|chrome\|display"
```

**Erwartung:** `sandbox: false`, `log_level: debug`
**Problem:** Falsche Config → Chrome-Start fehlgeschlagen

## VERBOTE

- NICHTS modifizieren (kein kubectl apply, kein git, kein helm)
- Nur lesen und analysieren
- Keine Chrome-Prozesse manuell starten (nur Diagnose)

## ANTWORT-FORMAT

```
## Zusammenfassung
[2-3 Sätze: Was ist die Root Cause?]

## Prüfpunkt 1: DevTools Port
[Ergebnis mit Beweis]

## Prüfpunkt 2: Chrome stderr/stdout
[Ergebnis mit Beweis]

## Prüfpunkt 3: Chrome Flags
[Ergebnis mit Beweis]

## Prüfpunkt 4: Shared Memory
[Ergebnis mit Beweis]

## Prüfpunkt 5: Display/Xvfb
[Ergebnis mit Beweis]

## Prüfpunkt 6: Chrome-Sandbox
[Ergebnis mit Beweis]

## Prüfpunkt 7: Library-Dependencies
[Ergebnis mit Beweis]

## Prüfpunkt 8: Helm Chart Config
[Ergebnis mit Beweis]

## Root Cause
[Diagnose mit konkretem Beweis]

## Empfohlener Fix
[Was muss geändert werden?]
```
