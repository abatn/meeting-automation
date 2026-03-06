from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/transcription/{recording_id}")
async def websocket_transcription_endpoint(websocket: WebSocket, recording_id: str):
    """
    WebSocket Route für die Fortschrittsanzeige der Transkription.
    Frontend verbindet sich hier mit ws://.../api/v1/websockets/transcription/{recording_id}
    """
    await manager.connect(websocket, recording_id)
    try:
        # Bestätigung an den Client senden
        await manager.send_personal_message(
            '{"status": "connected", "progress": 0, "message": "Connection established"}',
            websocket
        )

        # Verbindung offen halten und auf Client-Nachrichten (Ping) warten
        while True:
            # Wir warten hier nur passiv, da Updates über Redis reinkommen
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message("pong", websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, recording_id)
    except Exception as e:
        logger.error(f"WebSocket Error for recording {recording_id}: {e}")
        manager.disconnect(websocket, recording_id)
