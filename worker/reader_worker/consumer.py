import asyncio
import json
import uuid
from typing import Dict

import redis.asyncio as redis
from sqlalchemy import select

from .config import settings
from .database import get_db_session
from .fetcher import FeedFetcher
from .models import Feed


class JobConsumer:
    """Consumer that processes feed fetch jobs from Redis queue."""

    def __init__(self):
        self.redis_client = None
        self.fetcher = FeedFetcher()
        self.running = False
        self.active_tasks = set()

    async def get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.redis_url)
        return self.redis_client

    async def start(self):
        """Start consuming jobs."""
        self.running = True
        print("Starting job consumer...")

        # Create multiple consumer coroutines for concurrency
        consumers = [
            self._consume_jobs() for _ in range(min(settings.fetch_concurrency, 5))
        ]

        await asyncio.gather(*consumers)

    async def stop(self):
        """Stop consuming jobs."""
        self.running = False

        # Wait for active tasks to complete
        if self.active_tasks:
            print(f"Waiting for {len(self.active_tasks)} active tasks to complete...")
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

        await self.fetcher.close()
        if self.redis_client:
            await self.redis_client.close()

    async def _consume_jobs(self):
        """Consume jobs from Redis queue."""
        redis_conn = await self.get_redis()

        while self.running:
            try:
                # Block for job with timeout
                result = await redis_conn.brpop("rss:jobs", timeout=5)

                if result is None:
                    continue

                _, job_data = result
                job = json.loads(job_data.decode())

                # Process job in background
                task = asyncio.create_task(self._process_job(job))
                self.active_tasks.add(task)
                task.add_done_callback(self.active_tasks.discard)

            except Exception as e:
                print(f"Consumer error: {e}")
                await asyncio.sleep(1)

    async def _process_job(self, job: Dict):
        """Process a single fetch job."""
        try:
            feed_id = uuid.UUID(job["feed_id"])

            # Get feed from database
            async with get_db_session() as db:
                stmt = select(Feed).where(Feed.id == feed_id)
                result = await db.execute(stmt)
                feed = result.scalar_one_or_none()

                if not feed:
                    print(f"Feed {feed_id} not found, skipping job")
                    return

            print(f"Processing feed: {feed.url}")

            # Fetch feed
            result = await self.fetcher.fetch_feed(feed)

            # Publish status event
            await self._publish_fetch_status(result)

            if result["status"] == "success":
                print(
                    f"Successfully processed feed {feed.url}, {result['new_items']} new items"
                )
            elif result["status"] == "not_modified":
                print(f"Feed {feed.url} not modified")
            else:
                print(
                    f"Error processing feed {feed.url}: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            print(f"Job processing error: {e}")
            # Publish error event
            await self._publish_fetch_status(
                {
                    "status": "error",
                    "feed_id": job.get("feed_id", "unknown"),
                    "error": str(e),
                }
            )

    async def _publish_fetch_status(self, result: Dict):
        """Publish fetch status event."""
        try:
            redis_conn = await self.get_redis()

            event = {
                "type": "fetch_status",
                "timestamp": asyncio.get_event_loop().time(),
                "data": {
                    "feed_id": result["feed_id"],
                    "status": "ok" if result["status"] == "success" else "error",
                    "message": result.get("error"),
                },
            }

            await redis_conn.publish("rss:events", json.dumps(event))

        except Exception as e:
            print(f"Error publishing fetch status: {e}")
