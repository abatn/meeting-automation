import logging

from livekit.api import AccessToken, LiveKitAPI, VideoGrants
from livekit.protocol.egress import (
    EncodedFileOutput,
    EncodingOptionsPreset,
    RoomCompositeEgressRequest,
    StopEgressRequest,
    ListEgressRequest,
)
from livekit.protocol.room import CreateRoomRequest, DeleteRoomRequest

from app.core.config import settings

logger = logging.getLogger(__name__)


class LiveKitService:
    def __init__(self):
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = LiveKitAPI(
                url=settings.LIVEKIT_URL,
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
            )
        return self._api

    async def create_room(self, meeting_id: str):
        req = CreateRoomRequest()
        req.name = meeting_id
        req.empty_timeout = 300
        req.max_participants = 50
        room = await self.api.room.create_room(req)
        logger.info(f"LiveKit room created: {meeting_id} (sid={room.sid})")
        return room

    async def delete_room(self, meeting_id: str):
        req = DeleteRoomRequest()
        req.room = meeting_id
        await self.api.room.delete_room(req)
        logger.info(f"LiveKit room deleted: {meeting_id}")

    async def generate_token(self, meeting_id: str, user_id: str, can_publish: bool = True) -> str:
        token = (
            AccessToken(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
            .with_identity(user_id)
            .with_grants(VideoGrants(
                room_join=True,
                room=meeting_id,
                can_publish=can_publish,
                can_subscribe=True,
            ))
        )
        return token.to_jwt()

    async def start_egress(self, meeting_id: str, file_key: str) -> str:
        file_output = EncodedFileOutput()
        file_output.filepath = file_key
        file_output.s3.access_key = settings.S3_ACCESS_KEY
        file_output.s3.secret = settings.S3_SECRET_KEY
        file_output.s3.bucket = settings.LIVEKIT_EGRESS_BUCKET
        file_output.s3.endpoint = settings.S3_ENDPOINT
        file_output.s3.region = "us-east-1"
        # Force path-style URLs so MinIO can resolve host without DNS subdomain
        # routing (avoids `meeting-recordings.minio:9000` lookup failure).
        # See docs/LIVEKIT_PRODUCTION_HARDENING_ROADMAP.md Tier 1.1
        file_output.s3.force_path_style = True

        req = RoomCompositeEgressRequest()
        req.room_name = meeting_id
        req.preset = EncodingOptionsPreset.H264_720P_30
        req.audio_only = True
        req.file.CopyFrom(file_output)

        info = await self.api.egress.start_room_composite_egress(req)
        logger.info(f"Egress started for {meeting_id}: egress_id={info.egress_id}")
        return info.egress_id

    async def stop_egress(self, egress_id: str) -> None:
        """Stop an active egress recording."""
        req = StopEgressRequest()
        req.egress_id = egress_id
        await self.api.egress.stop_egress(req)
        logger.info(f"Egress stopped: egress_id={egress_id}")

    async def list_egress(self, meeting_id: str) -> list:
        """List active egress sessions for a room."""
        req = ListEgressRequest()
        req.room_name = meeting_id
        req.active = True
        response = await self.api.egress.list_egress(req)
        return list(response.items)
