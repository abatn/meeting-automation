from fastapi import FastAPI
from app.api.v1 import auth, meetings, recordings

app = FastAPI()

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(meetings.router, prefix="/api/v1/meetings", tags=["meetings"])
app.include_router(recordings.router, prefix="/api/v1/recordings", tags=["recordings"])

@app.get("/")
async def root():
    return {"message": "Hello Meeting Automation Backend!"}
