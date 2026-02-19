from typing import Optional
from datetime import datetime
from backend.app.models.action import Action
from backend.app.models.user import User

class NotificationService:
    async def send_email_notification(self, recipient_email: str, subject: str, body: str):
        """
        Sends an email notification.
        In a real application, this would integrate with an email sending library/service.
        """
        print(f"Sending email to {recipient_email} with subject: {subject}")
        print(f"Body: {body}")
        # TODO: Integrate with actual email sending service (e.g., SendGrid, Mailgun, SMTP)

    async def send_whatsapp_notification(self, recipient_phone: str, message: str):
        """
        Sends a WhatsApp notification.
        In a real application, this would integrate with a WhatsApp API service.
        """
        print(f"Sending WhatsApp message to {recipient_phone}: {message}")
        # TODO: Integrate with actual WhatsApp API (e.g., Twilio, WhatsApp Business API)

    async def send_new_action_notification(self, action: Action):
        """Sends a notification when a new action is created."""
        if action.assignee and action.assignee.email:
            subject = f"Neue Aktion zugewiesen: {action.description}"
            body = (
                f"Hallo {action.assignee.full_name},\n\n"
                f"Ihnen wurde eine neue Aktion zugewiesen:\n"
                f"Beschreibung: {action.description}\n"
                f"Fälligkeitsdatum: {action.due_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"Priorität: {action.priority if action.priority else 'N/A'}\n"
                f"Meeting: {action.meeting.title if action.meeting else 'N/A'}\n\n"
                f"Bitte überprüfen Sie diese Aktion und markieren Sie sie als erledigt, sobald sie abgeschlossen ist.\n\n"
                f"Mit freundlichen Grüßen,\nIhr Meeting Automation Team"
            )
            await self.send_email_notification(action.assignee.email, subject, body)
            # if action.assignee.phone_number:
            #     whatsapp_message = f"Neue Aktion zugewiesen: {action.description}. Fällig am {action.due_date.strftime('%Y-%m-%d')}. Meeting: {action.meeting.title if action.meeting else 'N/A'}"
            #     await self.send_whatsapp_notification(action.assignee.phone_number, whatsapp_message)

    async def send_action_update_notification(self, action: Action):
        """Sends a notification when an action is updated."""
        if action.assignee and action.assignee.email:
            subject = f"Aktion aktualisiert: {action.description}"
            body = (
                f"Hallo {action.assignee.full_name},\n\n"
                f"Eine Ihnen zugewiesene Aktion wurde aktualisiert:\n"
                f"Beschreibung: {action.description}\n"
                f"Status: {action.status.value}\n"
                f"Fälligkeitsdatum: {action.due_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"Priorität: {action.priority if action.priority else 'N/A'}\n"
                f"Meeting: {action.meeting.title if action.meeting else 'N/A'}\n\n"
                f"Mit freundlichen Grüßen,\nIhr Meeting Automation Team"
            )
            await self.send_email_notification(action.assignee.email, subject, body)

    async def send_action_reminder_notification(self, action: Action):
        """Sends a reminder notification for an action."""
        if action.assignee and action.assignee.email:
            subject = f"ERINNERUNG: Aktion überfällig oder fällig: {action.description}"
            body = (
                f"Hallo {action.assignee.full_name},\n\n"
                f"Dies ist eine Erinnerung für die folgende Aktion, die Ihnen zugewiesen wurde:\n"
                f"Beschreibung: {action.description}\n"
                f"Status: {action.status.value}\n"
                f"Fälligkeitsdatum: {action.due_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"Priorität: {action.priority if action.priority else 'N/A'}\n"
                f"Meeting: {action.meeting.title if action.meeting else 'N/A'}\n\n"
                f"Bitte stellen Sie sicher, dass diese Aktion rechtzeitig abgeschlossen wird.\n\n"
                f"Mit freundlichen Grüßen,\nIhr Meeting Automation Team"
            )
            await self.send_email_notification(action.assignee.email, subject, body)

    async def send_action_completion_notification(self, action: Action):
        """Sends a notification when an action is completed."""
        if action.assignee and action.assignee.email:
            subject = f"Aktion abgeschlossen: {action.description}"
            body = (
                f"Hallo {action.assignee.full_name},\n\n"
                f"Die Aktion '{action.description}' wurde als abgeschlossen markiert.\n"
                f"Abgeschlossen am: {action.completed_at.strftime('%Y-%m-%d %H:%M') if action.completed_at else 'N/A'}\n"
                f"Kommentar: {action.completion_comment if action.completion_comment else 'Kein Kommentar'}\n\n"
                f"Mit freundlichen Grüßen,\nIhr Meeting Automation Team"
            )
            await self.send_email_notification(action.assignee.email, subject, body)
        
        # Also notify the meeting organizer if different from assignee
        if action.meeting and action.meeting.organizer and action.meeting.organizer.email and \
           action.meeting.organizer.id != action.assigned_to:
            subject_organizer = f"Aktion abgeschlossen in Ihrem Meeting: {action.description}"
            body_organizer = (
                f"Hallo {action.meeting.organizer.full_name},\n\n"
                f"Eine Aktion aus Ihrem Meeting '{action.meeting.title}' wurde abgeschlossen:\n"
                f"Beschreibung: {action.description}\n"
                f"Zugewiesen an: {action.assignee.full_name if action.assignee else 'N/A'}\n"
                f"Abgeschlossen am: {action.completed_at.strftime('%Y-%m-%d %H:%M') if action.completed_at else 'N/A'}\n"
                f"Kommentar: {action.completion_comment if action.completion_comment else 'Kein Kommentar'}\n\n"
                f"Mit freundlichen Grüßen,\nIhr Meeting Automation Team"
            )
            await self.send_email_notification(action.meeting.organizer.email, subject_organizer, body_organizer)


notification_service = NotificationService()