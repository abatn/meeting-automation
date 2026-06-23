from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.middleware.audit_middleware import AuditMiddleware
from app.api.v1 import (
    auth,
    meetings,
    recordings,
    transcriptions,
    pv,
    actions,
    reports,
    webhooks,
    websockets,
    settings as settings_router,
    admin,
    billing,
    webhooks_stripe,
    team,
    rooms,
    audit,
    cms,
    livekit,
)
from app.core.websocket import manager
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Meeting Automation System...")

    # Ensure S3 Buckets exist (Auto-Healing)
    await ensure_s3_buckets_exist()

    # Start Redis WebSocket Listener task
    asyncio.create_task(manager.listen_to_redis())

    if settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized (dev mode)")
    else:
        logger.info("Database managed by Alembic (production mode)")
    yield
    # Shutdown
    logger.info("Shutting down...")


async def ensure_s3_buckets_exist():
    """Checks for required S3 buckets and creates them if missing."""
    import boto3
    from botocore.exceptions import ClientError
    
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    buckets = [settings.S3_BUCKET_NAME, "meeting-pdfs"]
    
    for bucket in buckets:
        try:
            # Check if bucket exists
            s3_client.head_bucket(Bucket=bucket)
            logger.info(f"S3 Bucket '{bucket}' exists.")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404' or error_code == 'NoSuchBucket':
                logger.warning(f"S3 Bucket '{bucket}' missing. Creating...")
                try:
                    s3_client.create_bucket(Bucket=bucket)
                    logger.info(f"S3 Bucket '{bucket}' created successfully.")
                except Exception as ce:
                    logger.error(f"Failed to create bucket '{bucket}': {ce}")
            else:
                logger.error(f"Error checking S3 bucket '{bucket}': {e}")

app = FastAPI(
    title="Meeting Automation API",
    description="Automated meeting transcription, PV generation, and action tracking",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit Middleware (ISO 27001)
app.add_middleware(AuditMiddleware)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = None
    try:
        body = await request.body()
    except Exception:
        pass
    logger.error(
        f"422 VALIDATION ERROR: path={request.url.path} method={request.method} "
        f"body={body!r} errors={exc.errors()}"
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# API Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(meetings.router, prefix="/api/v1/meetings", tags=["Meetings"])
app.include_router(recordings.router, prefix="/api/v1/recordings", tags=["Recordings"])
app.include_router(
    transcriptions.router, prefix="/api/v1/transcriptions", tags=["Transcriptions"]
)
app.include_router(pv.router, prefix="/api/v1/pv", tags=["Procès-Verbaux"])
app.include_router(actions.router, prefix="/api/v1/actions", tags=["Actions"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(websockets.router, prefix="/api/v1/websockets", tags=["WebSockets"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["System Admin"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(team.router, prefix="/api/v1/team", tags=["Team Management"])
app.include_router(rooms.router, prefix="/api/v1/rooms", tags=["Meeting Rooms"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit Logging"])
app.include_router(webhooks_stripe.router, prefix="/api/v1/webhooks/stripe", tags=["Stripe Webhooks"])
app.include_router(cms.router, prefix="/api/v1/cms", tags=["CMS"])
app.include_router(livekit.router, prefix="/api/v1", tags=["LiveKit"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
