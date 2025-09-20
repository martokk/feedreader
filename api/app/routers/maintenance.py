"""Maintenance router for dangerous operations."""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.redis import get_redis
from ..models.feed import Feed
from ..models.item import Item
from ..models.read_state import ReadState

router = APIRouter()


@router.delete("/items/all", status_code=status.HTTP_200_OK)
async def remove_all_feed_items(db: AsyncSession = Depends(get_db)):
    """Remove all feed items from the database.

    WARNING: This operation is irreversible and will delete all feed items
    and their associated read states. Feeds will appear as if they are being
    scanned for the first time.

    After deletion, all feeds will be queued for immediate refresh to re-fetch content.
    """
    try:
        # First delete all read states (foreign key dependency)
        read_state_delete_stmt = delete(ReadState)
        read_state_result = await db.execute(read_state_delete_stmt)
        read_states_deleted = read_state_result.rowcount

        # Then delete all items
        items_delete_stmt = delete(Item)
        items_result = await db.execute(items_delete_stmt)
        items_deleted = items_result.rowcount

        await db.commit()

        # After successful deletion, queue all feeds for immediate refresh
        feeds_queued = 0
        try:
            # Get all feeds
            feeds_stmt = select(Feed)
            feeds_result = await db.execute(feeds_stmt)
            feeds = feeds_result.scalars().all()

            if feeds:
                # Get Redis connection
                redis = await get_redis()

                # Queue refresh job for each feed
                for feed in feeds:
                    # Update next_run_at to now for immediate processing
                    feed.next_run_at = datetime.utcnow()

                    # Create job data
                    job_data = {
                        "job_id": str(uuid.uuid4()),
                        "feed_id": str(feed.id),
                        "scheduled_at": datetime.utcnow().isoformat(),
                        "url": feed.url,
                    }

                    # Enqueue job
                    await redis.lpush("rss:jobs", json.dumps(job_data))
                    feeds_queued += 1

                # Commit the next_run_at updates
                await db.commit()

        except Exception as queue_error:
            # Log the error but don't fail the main operation since items were already deleted
            print(f"Warning: Failed to queue feed refreshes after item deletion: {queue_error}")

        return {
            "message": "Successfully removed all feed items and queued feeds for refresh",
            "items_deleted": items_deleted,
            "read_states_deleted": read_states_deleted,
            "feeds_queued_for_refresh": feeds_queued,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove feed items: {str(e)}",
        )
