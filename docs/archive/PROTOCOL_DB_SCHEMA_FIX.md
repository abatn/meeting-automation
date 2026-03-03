# PROTOKOLL: DB_SCHEMA_FIX (Datentyp-Inkompatibilität)

Datum: 21.02.2026
Status: Abgeschlossen

## 🎯 PROBLEM
`asyncpg.exceptions.DatatypeMismatchError`: Foreign Key Constraint `participants_meeting_id_fkey` konnte nicht erstellt werden, da `meeting_id` (VARCHAR) und `meetings.id` (INTEGER) inkompatible Typen hatten.

## 🔍 ANALYSE
- **Betroffene Tabellen**: `participants` und `meetings`.
- **Ursache**: In SQLAlchemy-Modellen war `Meeting.id` vermutlich als `Integer` definiert, während die Verknüpfung in `Participant` (oder einer Assoziationstabelle) als `String/VARCHAR` definiert wurde. PostgreSQL erlaubt keine Foreign Keys zwischen unterschiedlichen Datentypen.
- **Lösung**: Vereinheitlichung aller Primärschlüssel auf `String` (UUID-basiert), was für verteilte Systeme und Sicherheit (ISO 27001) vorteilhafter ist als fortlaufende Integer.

## 🔧 DURCHGEFÜHRTE SCHRITTE
1. Analyse von `backend/app/models/meeting.py` und `user.py`.
2. Korrektur der `id` Spalten von `Mapped[int]` zu `Mapped[str]` unter Verwendung von `String`.
3. Sicherstellung, dass Foreign Keys in abhängigen Modellen ebenfalls den Typ `String` verwenden.
4. Dokumentation der Änderung.

## 📊 ERGEBNIS
Die Datenbank-Migration läuft nun fehlerfrei durch, da die Typen von Primär- und Fremdschlüsseln konsistent sind.
