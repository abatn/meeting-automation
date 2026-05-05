from fastapi import APIRouter

from . import (
    auth,
    meetings,
    recordings,
    transcriptions,
    pv,
    actions,
    reports,
    websockets,
    settings,
    audit,
)

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
router.include_router(recordings.router, prefix="/recordings", tags=["Recordings"])
router.include_router(
    transcriptions.router, prefix="/transcriptions", tags=["Transcriptions"]
)
router.include_router(pv.router, prefix="/pv", tags=["Procès-Verbaux"])
router.include_router(actions.router, prefix="/actions", tags=["Actions"])
router.include_router(reports.router, prefix="/reports", tags=["Reports"])
router.include_router(websockets.router, prefix="/websockets", tags=["WebSockets"])
router.include_router(settings.router, prefix="/settings", tags=["Settings"])
router.include_router(audit.router, prefix="/audit", tags=["Audit Logging"])
