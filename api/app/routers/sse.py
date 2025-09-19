import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ..core.config import settings
from ..core.redis import RSS_EVENTS_CHANNEL, get_redis

router = APIRouter(prefix="/sse", tags=["events"])


async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events stream."""
    redis = await get_redis()
    pubsub = redis.pubsub()

    try:
        # Subscribe to RSS events channel
        await pubsub.subscribe(RSS_EVENTS_CHANNEL)

        # Send initial connection event
        yield {
            "event": "connected",
            "data": json.dumps(
                {
                    "type": "connected",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {},
                }
            ),
        }

        # Heartbeat interval
        heartbeat_interval = settings.sse_heartbeat_ms / 1000.0
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                # Wait for message with timeout for heartbeat
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=heartbeat_interval,
                )

                if message and message["type"] == "message":
                    # Forward Redis message to SSE client
                    yield {"event": "message", "data": message["data"].decode()}
                    last_heartbeat = asyncio.get_event_loop().time()

            except asyncio.TimeoutError:
                # Send heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.utcnow().isoformat(),
                                "data": {},
                            }
                        ),
                    }
                    last_heartbeat = current_time

    except Exception as e:
        # Log error and close connection
        print(f"SSE error: {e}")
    finally:
        await pubsub.unsubscribe(RSS_EVENTS_CHANNEL)
        await pubsub.close()


@router.get("/events")
async def stream_events(request: Request):
    """Server-Sent Events endpoint for real-time updates."""
    return EventSourceResponse(
        event_stream(request),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": settings.frontend_origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )
