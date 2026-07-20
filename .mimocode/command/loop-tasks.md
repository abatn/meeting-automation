---
description: Read .loop.md and execute the next pending task from the meeting-automation task list
---

# Execute Loop Tasks

Read `.loop.md` and execute the next pending task. The user has sent this same prompt multiple times across sessions — this command standardizes the workflow.

## Prompt Template

```
DU BIST EIN AGENT, DER ARBEITEN MUSS.

Regeln:
1. Lies .loop.md
2. FIND EINE AUFGABE – nicht "vorschlagen", sondern FINDEN
3. MACH SIE – Code schreiben, Fehler fixen, Datei ändern
4. WENN DU NICHTS FINDEST: Analysiere den Code und schreibe einen konkreten Verbesserungsvorschlag

WICHTIG:
- Lies zuerst .loop.md für den aktuellen Stand
- Implementiere die nächste OFFENE Aufgabe
- Keine Vorschläge, sondern AUSFÜHRUNG
- Nach der Aufgabe: Update .loop.md mit Status
- Dokumentiere HARTE LESSONS in .loop.md

$ARGUMENTS
```

## Procedure

1. **Read `.loop.md`** — Parse the current phase status and identify open tasks
2. **Find next task** — Look for `OFFEN` (open) items or incomplete phases
3. **Execute** — Write code, fix bugs, modify files as needed
4. **Verify** — Run tests or syntax checks where applicable
5. **Update `.loop.md`** — Mark task complete, add HARTE LESSONS

## Notes

- The `$ARGUMENTS` placeholder can be used to specify a particular phase or task
- If no arguments provided, execute the first open task from the latest phase
- User communicates in German — match language in `.loop.md` updates
- Always check AGENTS.md for project-specific rules before making changes
