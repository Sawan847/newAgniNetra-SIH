"""Real-time Intelligence Event Stream (SSE) API endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.events import broadcaster

router = APIRouter()


@router.get(
    "/events/stream",
    summary="Server-Sent Events stream for live satellite detections and alerts",
)
async def stream_live_events():
    """Stream live detection telemetry, alert notifications, and system events via SSE."""
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
