from app.tasks.celery_app import celery_app

@celery_app.task
def transcribe_audio_task(recording_id: int):
    # TODO: Implement audio transcription logic
    print(f"Transcribing audio for recording {recording_id}")