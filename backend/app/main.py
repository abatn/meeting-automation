from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import logging
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging_config import setup_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware
from app.api import deps
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
    contact,
)
from app.core.websocket import manager
import asyncio

# Configure structured logging (JSON for Loki, text for local dev)
LOG_JSON = os.getenv("LOG_JSON", "true").lower() == "true"
setup_logging(json_format=LOG_JSON)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Meeting Automation System...")

    # Ensure S3 Buckets exist (Auto-Healing)
    await ensure_s3_buckets_exist()

    # Ensure CMS Pricing Plans are populated (Auto-Healing)
    await ensure_pricing_plans_exist()

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
    # Phase 97: Tenant-Buckets werden bei Tenant-Registrierung dynamisch erstellt (get_bucket_name(client_id))
    
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

async def ensure_pricing_plans_exist():
    """Populates CMS pricing_plans table if empty (single source of truth)."""
    import uuid as _uuid
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.cms import PricingPlan

    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(PricingPlan))
        if count and count > 0:
            logger.info(f"CMS pricing_plans: {count} rows exist.")
            return

        logger.info("CMS pricing_plans empty — populating defaults...")
        plans = [
            {
                "id": str(_uuid.uuid4()),
                "name": {"en": "Gratuit", "fr": "Gratuit", "ar": "مجاني"},
                "plan_code": "GRATUIT",
                "price_monthly": 0,
                "price_yearly": 0,
                "minutes_included": 120,
                "features": [
                    {"en": "Basic Transcription", "fr": "Transcription de base"},
                    {"en": "1 PV per meeting", "fr": "1 PV par réunion"},
                    {"en": "Email notifications", "fr": "Notifications par email"},
                ],
                "is_popular": False,
                "order": 1,
                "is_active": True,
            },
            {
                "id": str(_uuid.uuid4()),
                "name": {"en": "Pro", "fr": "Pro"},
                "plan_code": "PRO",
                "price_monthly": 99,
                "price_yearly": 990,
                "minutes_included": 1800,
                "features": [
                    {"en": "Sentinel LLM Summarization", "fr": "Résumé par Sentinel LLM"},
                    {"en": "Speaker Voice ID", "fr": "Identification vocale"},
                    {"en": "PDF Export", "fr": "Export PDF"},
                    {"en": "Advanced Analytics", "fr": "Analyses avancées"},
                ],
                "is_popular": True,
                "order": 2,
                "is_active": True,
            },
            {
                "id": str(_uuid.uuid4()),
                "name": {"en": "Enterprise", "fr": "Entreprise"},
                "plan_code": "ENTREPRISE",
                "price_monthly": 499,
                "price_yearly": 4990,
                "minutes_included": 3600,
                "features": [
                    {"en": "Everything in Pro", "fr": "Tout dans Pro"},
                    {"en": "Meeting Analytics", "fr": "Analytiques de réunion"},
                    {"en": "Voice Biometric Auth", "fr": "Authentification biométrique vocale"},
                    {"en": "External Speaker CRM", "fr": "CRM intervenants externes"},
                    {"en": "Priority Support", "fr": "Support prioritaire"},
                ],
                "is_popular": False,
                "order": 3,
                "is_active": True,
            },
        ]
        for plan in plans:
            db.add(PricingPlan(**plan))
        await db.commit()
        logger.info("CMS pricing_plans: 3 plans created (GRATUIT/PRO/ENTREPRISE).")


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

# Metrics Middleware (Prometheus HTTP request tracking)
app.add_middleware(MetricsMiddleware)


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


# Prometheus Metrics — Professional Pipeline Monitoring
from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST

# Pipeline Stage Duration (pro Stage messen)
PIPELINE_STAGE_DURATION = Histogram(
    "pipeline_stage_duration_seconds",
    "Pipeline stage processing duration",
    ["stage"],
    buckets=[0.5, 1, 2, 5, 10, 15, 30, 60, 90, 120, 180, 300],
)

# Pipeline Business Metrics (ISO 27001 A.8.26 Multi-Tenant: client_id Labels)
PIPELINE_RECORDINGS = Counter(
    "pipeline_recordings_total",
    "Total recordings processed",
    ["status", "client_id"],  # completed, failed + tenant isolation
)
PIPELINE_TRANSCRIPTIONS = Counter(
    "pipeline_transcriptions_total",
    "Total transcriptions generated",
    ["status", "language", "client_id"],  # completed, failed + ar, fr, en + tenant isolation
)
PIPELINE_PV_SECTIONS = Counter(
    "pipeline_pv_sections_total",
    "Total PV sections generated",
    ["client_id"],  # tenant isolation
)
PIPELINE_ACTIONS = Counter(
    "pipeline_actions_total",
    "Total actions created",
    ["client_id"],  # tenant isolation
)

# Service Health Metrics (extern APIs)
SERVICE_REQUEST_DURATION = Histogram(
    "service_request_duration_seconds",
    "External service request duration",
    ["service", "operation"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)
SERVICE_REQUEST_ERRORS = Counter(
    "service_request_errors_total",
    "External service request errors",
    ["service", "error_type"],  # timeout, 4xx, 5xx
)

# Celery Queue Metrics
CELERY_QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Number of messages in Celery queue",
    ["queue"],
)

# Legacy Metrics (backwards compatibility)
PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Total pipeline processing duration (legacy)",
    ["stage"],
    buckets=[1, 5, 10, 15, 30, 60, 90, 120],
)
PIPELINE_FAILURES = Counter(
    "pipeline_failures_total",
    "Total pipeline failures",
    ["stage", "reason"],
)
ACTIVE_RECORDINGS = Gauge(
    "active_recordings",
    "Number of recordings currently being processed",
)
STORAGE_USAGE = Gauge(
    "storage_usage_bytes",
    "S3 storage usage per tenant",
    ["client_id"],  # ISO 27001 A.8.26 Multi-Tenant
)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint. Internal only (PodIP, not via Ingress)."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


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
app.include_router(contact.router, prefix="/api/v1", tags=["Contact"])
app.include_router(livekit.router, prefix="/api/v1", tags=["LiveKit"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
