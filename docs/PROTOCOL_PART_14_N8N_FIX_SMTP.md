# PROTOKOLL: PART 14 - n8n Workflow Fix (SendGrid to SMTP)

Datum: 21.02.2026
Status: Abgeschlossen

🎯 ZIEL
Korrektur des n8n Workflows `daily-reminders.json`, um die Abhängigkeit von einem spezifischen SendGrid-Knoten zu entfernen und stattdessen eine universelle SMTP-Lösung zu nutzen.

🔧 TECHNOLOGIEN
- n8n Workflow Engine
- SMTP Protocol
- JSON Configuration

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. Analyse der `daily-reminders.json` Fehlermeldung bezüglich inkompatibler Knoten.
2. Entfernung des `n8n-nodes-base.emailSendGrid` Knotens.
3. Implementierung des `n8n-nodes-base.emailSend` (Standard SMTP) Knotens.
4. Mapping der dynamischen Variablen für:
   - Empfänger: `{{$json["manager_email"]}}`
   - Betreff: `Action Item Escalation: {{$json["title"]}}`
   - Body: Zusammenfassung des overdue Status und des Zuweisungsempfängers.
5. Verknüpfung des neuen Knotens mit der bestehenden `IF`-Logik.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Herausforderung**: SendGrid-Knoten sind oft nicht in allen n8n-Umgebungen standardmäßig aktiv.
- **Lösung**: Umstellung auf SMTP, da die Zugangsdaten bereits in der `.env` des Projekts vorhanden sind (SMTP_HOST, SMTP_PORT, etc.).

🔗 ZUSAMMENHANG ZUM PROJEKT
Gewährleistet die zuverlässige Benachrichtigung von Managern bei überfälligen Aufgaben (Action Items), was ein Kernbestandteil des automatisierten Workflows ist.

📊 ERGEBNIS
Ein valider, portabler n8n-Workflow, der ohne zusätzliche Knoten-Installationen in der Standard-Infrastruktur funktioniert.