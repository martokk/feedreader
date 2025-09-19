import asyncio
import json
import uuid
from datetime import datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import select, update

from .config import settings
from .database import get_db_session
from .models import Feed


class FeedScheduler:
    """Scheduler that enqueues feed fetch jobs."""

    def __init__(self):
        self.redis_client = None
        self.running = False

    async def get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.redis_url)
        return self.redis_client

    async def start(self):
        """Start the scheduler loop."""
        self.running = True
        print("Starting feed scheduler...")

        while self.running:
            try:
                await self._schedule_feeds()
                await asyncio.sleep(settings.scheduler_tick_seconds)
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(settings.scheduler_tick_seconds)

    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()

    async def _schedule_feeds(self):
        """Check for feeds due to run and enqueue jobs."""
        async with get_db_session() as db:
            # Get feeds that are due to run
            now = datetime.utcnow()
            stmt = (
                select(Feed)
                .where(Feed.next_run_at <= now)
                .order_by(Feed.next_run_at)
                .limit(settings.scheduler_batch_size)
            )

            result = await db.execute(stmt)
            feeds = result.scalars().all()

            if not feeds:
                return

            print(f"Scheduling {len(feeds)} feeds for fetching")

            redis_conn = await self.get_redis()

            for feed in feeds:
                # Create job
                job_data = {
                    "job_id": str(uuid.uuid4()),
                    "feed_id": str(feed.id),
                    "scheduled_at": datetime.utcnow().isoformat(),
                    "url": feed.url,
                }

                # Enqueue job
                await redis_conn.lpush("rss:jobs", json.dumps(job_data))

                # Update next_run_at to prevent duplicate scheduling
                next_run_at = now + timedelta(seconds=feed.interval_seconds)
                stmt = (
                    update(Feed)
                    .where(Feed.id == feed.id)
                    .values(next_run_at=next_run_at, updated_at=now)
                )
                await db.execute(stmt)

            await db.commit()
