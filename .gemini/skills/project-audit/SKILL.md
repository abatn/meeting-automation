# Project Audit Skill (ISO 27001)

Diese Skill spezialisiert den Agenten auf Sicherheits-Audits und Compliance-Prüfungen.

## Kompetenzen
- Überprüfung der Einhaltung von ISO 27001 Standards im Code.
- Auditierung der Field-Level Encryption für Transkriptionen und PVs.
- Validierung der Audit-Logging-Middleware.
- Prüfung der API-Sicherheit (Authentication & Authorization).

## Anweisungen
- Prüfe bei jeder Code-Änderung, ob sensible Daten (PII) unverschlüsselt gespeichert werden.
- Stelle sicher, dass alle administrativen Aktionen im `audit_log` erfasst werden.
- Verifiziere die Schlüssel-Rotation und die sichere Handhabung des `ENCRYPTION_KEY`.
- Achte auf SQL-Injection und XSS-Schutz in den API-Routen.
