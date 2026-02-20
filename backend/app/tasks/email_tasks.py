from app.tasks.celery_app import celery_app

@celery_app.task
def send_email_task(email_to: str, subject: str, body: str):
    # TODO: Implement actual email sending logic
    print(f"Sending email to {email_to} with subject '{subject}'")