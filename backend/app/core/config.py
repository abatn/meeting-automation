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

    # Mistral AI API Configuration
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "your-mistral-api-key")
    MISTRAL_API_BASE_URL: str = os.getenv("MISTRAL_API_BASE_URL", "https://api.mistral.ai/v1")
    MISTRAL_API_MODEL: str = os.getenv("MISTRAL_API_MODEL", "mistral-tiny")
    MISTRAL_API_TEMPERATURE: float = float(os.getenv("MISTRAL_API_TEMPERATURE", "0.7"))
    MISTRAL_API_MAX_TOKENS: int = int(os.getenv("MISTRAL_API_MAX_TOKENS", "1000"))
    MISTRAL_API_MAX_RETRIES: int = int(os.getenv("MISTRAL_API_MAX_RETRIES", "3"))
    MISTRAL_API_RETRY_DELAY: int = int(os.getenv("MISTRAL_API_RETRY_DELAY", "2"))
    MISTRAL_API_TIMEOUT: int = int(os.getenv("MISTRAL_API_TIMEOUT", "10"))
    MOCK_MISTRAL_API: bool = os.getenv("MOCK_MISTRAL_API", "True").lower() == "true"

    # Whisper API Configuration
    WHISPER_API_RETRIES: int = int(os.getenv("WHISPER_API_RETRIES", "3"))
    WHISPER_API_RETRY_DELAY_SECONDS: int = int(os.getenv("WHISPER_API_RETRY_DELAY_SECONDS", "2"))
    WHISPER_API_URL: str = os.getenv("WHISPER_API_URL", "http://localhost:9001/transcribe")
    WHISPER_API_TIMEOUT_SECONDS: int = int(os.getenv("WHISPER_API_TIMEOUT_SECONDS", "30"))

settings = Settings()
