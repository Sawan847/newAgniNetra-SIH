"""Real-time Event Broadcaster — Server-Sent Events (SSE) for live intelligence."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Manages connected SSE client queues and broadcasts real-time events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Bind the application loop so synchronous database workers can publish."""
        self._loop = loop

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Enqueue an invalidation after commit; safe to call from worker threads."""
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._deliver, event_type, data)

    def _deliver(self, event_type: str, data: dict[str, Any]) -> None:
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for queue in list(self._subscribers):
            if queue.full():
                queue.get_nowait()  # Invalidation stream; the client refetches current state.
            queue.put_nowait(payload)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Register a new client queue and stream SSE messages."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        logger.info("SSE client subscribed. Active connections: %d", len(self._subscribers))

        try:
            # Yield initial connection confirmation
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'clients': len(self._subscribers)})}\n\n"

            while True:
                try:
                    # Wait for next event or 15s keepalive
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    # Send comment keepalive to prevent browser/proxy connection drop
                    yield ": ping\n\n"
        finally:
            self._subscribers.discard(queue)
            logger.info("SSE client disconnected. Remaining connections: %d", len(self._subscribers))

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event payload to all connected clients."""
        self._deliver(event_type, data)


broadcaster = EventBroadcaster()
