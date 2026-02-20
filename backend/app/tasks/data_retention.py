from app.tasks.celery_app import celery_app

@celery_app.task
def cleanup_old_data_task():
    # TODO: Implement data retention logic
    print("Cleaning up old data")