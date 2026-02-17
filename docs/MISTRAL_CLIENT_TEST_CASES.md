# Mistral Client Integration Test Cases

This document outlines test cases for validating the Mistral Client integration.

## TESTFALL_MC01: Erfolgreiche PV-Generierung
-------------------------------------------
**Ziel:** Prüfen ob PV aus Transkription generiert wird.

**Vorgehen:**
1. Mock-Transkription mit Testdaten erstellen.
2. `mistral_client.generate_pv(transcription)` aufrufen.
3. Response parsen.

**Erwartet:** Strukturierte PV mit Content, Decisions, Actions.

## TESTFALL_MC02: Retry-Logik bei Timeout
-------------------------------------------
**Ziel:** Prüfen ob Retry bei temporären Fehlern funktioniert.

**Vorgehen:**
1. Mistral-API Mocken mit 2x Timeout, dann Success.
2. `client.call_mistral_api()` aufrufen.
3. Anzahl Attempts loggen.

**Erwartet:** 3 Versuche, finaler Success.

## TESTFALL_MC03: Rate-Limiting Handling
-------------------------------------------
**Ziel:** Prüfen Verhalten bei Rate-Limits.

**Vorgehen:**
1. API Mocken mit 429 Rate-Limit Error.
2. Exponential Backoff beobachten.
3. Nach max Retries Fehler werfen.

**Erwartet:** Korrekte Backoff-Zeiten, finaler Fehler.

## TESTFALL_MC04: Prompt-Template Validierung
-------------------------------------------
**Ziel:** Prüfen ob alle Platzhalter ersetzt werden.

**Vorgehen:**
1. Jedes Prompt-Template mit Testdaten füllen.
2. Template-Variablen prüfen auf Vollständigkeit.
3. Länge und Format validieren.

**Erwartet:** Keine unbelegten Platzhalter, korrektes Format.