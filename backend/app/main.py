from fastapi import FastAPI
import logging

from fastapi import FastAPI
from backend.app.api.v1 import auth, meetings, recordings, pv, users, transcriptions, actions, reports, audit
from backend.app.middleware.audit_middleware import AuditMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(AuditMiddleware)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(meetings.router, prefix="/api/v1/meetings", tags=["meetings"])
app.include_router(recordings.router, prefix="/api/v1/recordings", tags=["recordings"])
app.include_router(transcriptions.router, prefix="/api/v1/transcriptions", tags=["transcriptions"])
app.include_router(pv.router, prefix="/api/v1/pv", tags=["pv"])
app.include_router(actions.router, prefix="/api/v1/actions", tags=["actions"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])

@app.get("/")
async def root():
    return {"message": "Hello Meeting Automation Backend!"}
