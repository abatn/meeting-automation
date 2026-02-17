# Transaction Test Cases

This document outlines test cases for validating transaction handling in the application.

## TESTFALL_TR01: Erfolgreiche Transaktion
----------------------------------------
**Ziel:** Prüfen ob mehrere DB-Operationen in einer Transaktion funktionieren.

**Vorgehen:**
1. Transaktion starten.
2. Meeting erstellen.
3. PV für Meeting erstellen.
4. Aktionen für PV erstellen.
5. Transaktion committen.

**Erwartet:** Alle 3 Objekte in DB, konsistente IDs.

## TESTFALL_TR02: Rollback bei Fehler
----------------------------------------
**Ziel:** Prüfen ob Rollback bei Fehler funktioniert.

**Vorgehen:**
1. Transaktion starten.
2. Meeting erstellen.
3. PV erstellen (mit falscher `meeting_id` provozieren, um einen Fehler auszulösen).
4. Aktion erstellen (sollte nicht erreicht werden).
5. Fehler fangen und Rollback ausführen.

**Erwartet:** Keine Änderungen in DB, Meeting nicht gespeichert.

## TESTFALL_TR03: Verschachtelte Transaktionen
----------------------------------------
**Ziel:** Prüfen Verhalten bei Service-Aufrufen innerhalb einer Transaktion.

**Vorgehen:**
1. Service A startet Transaktion.
2. Service A ruft Service B auf.
3. Service B macht DB-Operation.
4. Service B wirft Fehler.

**Erwartet:** Korrektes Rollback aller Operationen.

## TESTFALL_TR04: Concurrency
----------------------------------------
**Ziel:** Prüfen auf Race Conditions.

**Vorgehen:**
1. Zwei parallele Requests auf gleiches Meeting.
2. Beide versuchen PV zu aktualisieren.
3. Letzter Commit gewinnt oder Fehler wird korrekt behandelt.

**Erwartet:** Keine Datenkorruption, konsistenter Endzustand.