import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Meeting Automation Backend"
    PROJECT_VERSION: str = "1.0.0"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sql_app.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # S3 / MinIO Configuration
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")
    S3_REGION_NAME: str = os.getenv("S3_REGION_NAME", "us-east-1")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "meeting-recordings")

    # Mistral Settings
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_API_URL: str = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1")
    MISTRAL_MODEL_NAME: str = os.getenv("MISTRAL_MODEL_NAME", "mistral-large-latest")
    MISTRAL_TEMPERATURE: float = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
    MISTRAL_MAX_TOKENS: int = int(os.getenv("MISTRAL_MAX_TOKENS", "2000"))
    MISTRAL_API_TIMEOUT: int = int(os.getenv("MISTRAL_API_TIMEOUT", "60"))
    MISTRAL_API_MAX_RETRIES: int = int(os.getenv("MISTRAL_API_MAX_RETRIES", "3"))
    MISTRAL_API_RETRY_DELAY: int = int(os.getenv("MISTRAL_API_RETRY_DELAY", "2"))

    # Whisper API Configuration
    WHISPER_API_RETRIES: int = int(os.getenv("WHISPER_API_RETRIES", "3"))
    WHISPER_API_RETRY_DELAY_SECONDS: int = int(os.getenv("WHISPER_API_RETRY_DELAY_SECONDS", "2"))
    WHISPER_API_URL: str = os.getenv("WHISPER_API_URL", "http://localhost:9001/transcribe")
    WHISPER_API_TIMEOUT_SECONDS: int = int(os.getenv("WHISPER_API_TIMEOUT_SECONDS", "30"))

    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_TASK_MAX_RETRIES: int = int(os.getenv("CELERY_TASK_MAX_RETRIES", "3"))
    CELERY_TASK_DEFAULT_RETRY_DELAY: int = int(os.getenv("CELERY_TASK_DEFAULT_RETRY_DELAY", "2"))

settings = Settings()
