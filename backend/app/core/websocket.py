import json
import logging
from typing import Dict, List
from fastapi import WebSocket
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Dictionary, um alle aktiven Verbindungen pro Recording zu speichern
        # Format: {"recording_id": [websocket1, websocket2, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Asynchroner Redis-Client für Pub/Sub
        self.redis_client = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0")
        self.pubsub = self.redis_client.pubsub()

    async def connect(self, websocket: WebSocket, recording_id: str):
        """Verbindung akzeptieren und im Dictionary speichern"""
        await websocket.accept()
        if recording_id not in self.active_connections:
            self.active_connections[recording_id] = []
        self.active_connections[recording_id].append(websocket)
        logger.info(f"WebSocket Client connected for recording {recording_id}")

    def disconnect(self, websocket: WebSocket, recording_id: str):
        """Verbindung aus dem Dictionary entfernen"""
        if recording_id in self.active_connections:
            if websocket in self.active_connections[recording_id]:
                self.active_connections[recording_id].remove(websocket)
            if not self.active_connections[recording_id]:
                del self.active_connections[recording_id]
        logger.info(f"WebSocket Client disconnected for recording {recording_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Direktnachricht an einen spezifischen Client senden"""
        await websocket.send_text(message)

    async def broadcast(self, message: str, recording_id: str):
        """Nachricht an alle Clients senden, die dieses Recording verfolgen"""
        if recording_id in self.active_connections:
            disconnected_clients = []
            for connection in self.active_connections[recording_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.warning(f"Error sending message to client: {e}")
                    disconnected_clients.append(connection)
            
            # Fehlerhafte Verbindungen aufräumen
            for connection in disconnected_clients:
                self.disconnect(connection, recording_id)

    async def listen_to_redis(self):
        """Hintergrund-Task: Auf Redis Pub/Sub Kanälen lauschen"""
        await self.pubsub.psubscribe("transcription_status_*")
        logger.info("Subscribed to Redis pattern 'transcription_status_*'")
        
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "pmessage":
                    # Channel Name auswerten, um die recording_id zu extrahieren
                    channel = message["channel"].decode("utf-8")
                    recording_id = channel.replace("transcription_status_", "")
                    
                    data = message["data"].decode("utf-8")
                    logger.debug(f"Redis Broadcast received for {recording_id}: {data}")
                    
                    # An die entsprechenden WebSockets verteilen
                    await self.broadcast(data, recording_id)
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")
            
# Singleton-Instanz für die gesamte App
manager = ConnectionManager()
