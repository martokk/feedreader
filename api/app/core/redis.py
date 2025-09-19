import asyncio
import json
from typing import Any, Dict

import redis.asyncio as redis

from .config import settings

# Redis connection
redis_client: redis.Redis = None


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(settings.redis_url)
    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def publish_event(channel: str, event_type: str, data: Dict[str, Any]):
    """Publish an event to Redis pub/sub channel."""
    redis_conn = await get_redis()
    event = {
        "type": event_type,
        "timestamp": asyncio.get_event_loop().time(),
        "data": data,
    }
    await redis_conn.publish(channel, json.dumps(event))


# Constants
RSS_EVENTS_CHANNEL = "rss:events"
