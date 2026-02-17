from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .meetings import router as meetings_router
from .recordings import router as recordings_router
from .transcriptions import router as transcriptions_router
from .actions import router as actions_router
from .pv import router as pv_router
from .reports import router as reports_router # New router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(meetings_router, prefix="/meetings", tags=["meetings"])
api_router.include_router(recordings_router, prefix="/recordings", tags=["recordings"])
api_router.include_router(transcriptions_router, prefix="/transcriptions", tags=["transcriptions"])
api_router.include_router(actions_router, prefix="/actions", tags=["actions"])
api_router.include_router(pv_router, prefix="/pv", tags=["pv"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"]) # Include new router