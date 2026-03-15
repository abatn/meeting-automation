from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Meeting Automation"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://meeting_user:meeting_password@postgres/meeting_db"
    )

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    # Fixed secret key for development to prevent logout on every restart
    SECRET_KEY: str = "dev-secret-key-fix-2026-ensure-session-stability"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Production standard (30 mins)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: bytes = b"12345678901234567890123456789012"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # S3 Storage
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minio_user"
    S3_SECRET_KEY: str = "minio_password"
    S3_BUCKET_NAME: str = "meeting-recordings"

    # AI Services
    OPENAI_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    GLADIA_API_KEY: str = ""
    HUGGINGFACE_TOKEN: str = ""

    # Email
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@example.com"

    # WhatsApp Business API
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v18.0"
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_TOKEN: str = ""

    # n8n
    N8N_WEBHOOK_URL: str = "http://n8n:5678/webhook"
    N8N_WEBHOOK_MEETING_CREATED: str = "http://n8n:5678/webhook/meeting-created"
    N8N_WEBHOOK_AUDIO_UPLOADED: str = "http://n8n:5678/webhook/audio-uploaded"
    N8N_WEBHOOK_PV_VALIDATED: str = "http://n8n:5678/webhook/pv-validated"
    N8N_WEBHOOK_DAILY_REMINDER: str = "http://n8n:5678/webhook/daily-reminders"
    N8N_WEBHOOK_TRANSCRIPTION_COMPLETED: str = (
        "http://n8n:5678/webhook/transcription-completed"
    )

    # Security
    INTERNAL_API_SECRET: str = "super-secret-automation-key-2026"
    BACKEND_CALLBACK_URL: str = "http://backend:8000/api/v1/webhooks"

    # Celery
    CELERY_BROKER_URL: str = "amqp://rabbit_user:rabbit_password@rabbitmq:5672//"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
