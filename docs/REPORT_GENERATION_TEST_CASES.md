# Report Generation Test Cases

This document outlines test cases for validating report generation (currently synchronous - potential problem).

## TESTFALL_RG01: PDF-Generierung mit Mock-Daten
-----------------------------------------------
**Ziel:** Prüfen ob PDF korrekt generiert wird.

**Vorgehen:**
1. Meeting mit PV und Aktionen erstellen.
2. `report_service.generate_pdf(meeting_id)` aufrufen.
3. Prüfen ob PDF-Datei erstellt wurde.
4. Prüfen ob Inhalt korrekt (minimale Validierung).

**Erwartet:** Gültige PDF-Datei mit Meeting-Daten.

## TESTFALL_RG02: DOCX-Generierung mit Mock-Daten
-----------------------------------------------
**Ziel:** Prüfen ob DOCX korrekt generiert wird.

**Vorgehen:**
1. Analog PDF-Test.

**Erwartet:** Gültige DOCX-Datei.

## TESTFALL_RG03: Performance-Test (Blockierung)
-----------------------------------------------
**Ziel:** Blockierungs-Potential messen.

**Vorgehen:**
1. Mehrere parallele Report-Requests.
2. Response-Zeiten messen.
3. CPU-Auslastung beobachten.

**Erwartet:** Requests werden sequentiell verarbeitet, hohe Latenz.
**Hinweis:** Dient als Baseline für Async-Implementierung.