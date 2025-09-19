import uuid
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse

import feedparser
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper

from ..core.database import get_db
from ..core.redis import get_redis
from ..models import Feed, Item, ReadState
from ..schemas.feed import (
    FeedCreate,
    FeedResponse,
    FeedStats,
    FeedUpdate,
    FeedValidation,
)

router = APIRouter(prefix="/feeds", tags=["feeds"])


class FeedCategoriesUpdate(BaseModel):
    """Schema for updating feed categories."""

    category_ids: List[uuid.UUID]


@router.get("/", response_model=List[FeedResponse])
async def get_feeds(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Get all feeds."""
    stmt = (
        select(
            Feed,
            func.count(Item.id)
            .filter(or_(ReadState.read_at.is_(None), ReadState.item_id.is_(None)))
            .label("unread_count"),
        )
        .outerjoin(Item, Feed.id == Item.feed_id)
        .outerjoin(ReadState, Item.id == ReadState.item_id)
        .group_by(Feed.id)
        .offset(skip)
        .limit(limit)
        .order_by(Feed.created_at.desc())
    )
    result = await db.execute(stmt)
    feeds_with_unread_count = result.all()

    feeds_response = []
    for feed, unread_count in feeds_with_unread_count:
        feed_data = {
            attr.key: getattr(feed, attr.key)
            for attr in class_mapper(Feed).iterate_properties
            if attr.key not in ["items", "categories", "fetch_logs"]
        }
        feed_data["unread_count"] = unread_count
        feeds_response.append(FeedResponse(**feed_data))

    return feeds_response


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(feed_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single feed by ID."""
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    return feed


@router.get("/{feed_id}/stats", response_model=FeedStats)
async def get_feed_stats(feed_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get statistics for a specific feed."""
    # Check if feed exists
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Get total items count
    total_items_stmt = select(func.count(Item.id)).where(Item.feed_id == feed_id)
    total_items_result = await db.execute(total_items_stmt)
    total_items = total_items_result.scalar() or 0

    # Get unread items count
    unread_items_stmt = (
        select(func.count(Item.id))
        .select_from(Item)
        .outerjoin(ReadState, ReadState.item_id == Item.id)
        .where(Item.feed_id == feed_id)
        .where(or_(ReadState.read_at.is_(None), ReadState.item_id.is_(None)))
    )
    unread_items_result = await db.execute(unread_items_stmt)
    unread_items = unread_items_result.scalar() or 0

    return FeedStats(
        feed_id=feed_id,
        total_items=total_items,
        unread_items=unread_items,
        last_fetch_at=feed.last_fetch_at,
        last_fetch_status=feed.last_status,
        next_run_at=feed.next_run_at,
    )


@router.post("/validate", response_model=FeedValidation)
async def validate_feed_url(url: str = Query()):
    """Validate a feed URL and get basic feed information."""
    try:
        # Parse the feed to validate it
        parsed_feed = feedparser.parse(url)

        if parsed_feed.bozo:
            # Provide user-friendly error message for parsing failures
            error_str = str(parsed_feed.bozo_exception).lower()
            if "syntax error" in error_str:
                error_message = "The URL does not contain valid RSS/Atom feed content. Please check the URL and try again."
            else:
                error_message = "The URL does not appear to be a valid RSS/Atom feed. Please check the URL and try again."

            return FeedValidation(
                url=url,
                is_valid=False,
                error_message=error_message,
            )

        if not parsed_feed.feed:
            return FeedValidation(
                url=url,
                is_valid=False,
                error_message="No feed data found at the URL",
            )

        feed_title = parsed_feed.feed.get("title", "").strip()

        return FeedValidation(
            url=url,
            is_valid=True,
            feed_title=feed_title if feed_title else None,
        )

    except Exception as e:
        return FeedValidation(
            url=url,
            is_valid=False,
            error_message=f"Error validating feed: {str(e)}",
        )


@router.post("/{feed_id}/refresh", response_model=dict)
async def refresh_feed(feed_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger a feed refresh."""
    # Check if feed exists
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    try:
        # Update next_run_at to now for immediate processing
        feed.next_run_at = datetime.utcnow()
        await db.commit()

        # Enqueue refresh job
        redis = await get_redis()
        job_data = {
            "job_id": str(uuid.uuid4()),
            "feed_id": str(feed.id),
            "scheduled_at": datetime.utcnow().isoformat(),
        }
        await redis.lpush("rss:jobs", str(job_data))

        return {
            "status": "success",
            "message": f"Feed refresh queued for {feed.title or feed.url}",
            "feed_id": str(feed.id),
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue feed refresh",
        )


@router.post("/", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(feed_data: FeedCreate, db: AsyncSession = Depends(get_db)):
    """Create a new feed."""
    # Extract host for per_host_key
    parsed_url = urlparse(feed_data.url)
    per_host_key = parsed_url.netloc

    # Create feed with next_run_at set to now + 5 seconds for immediate processing
    next_run_at = datetime.utcnow() + timedelta(seconds=5)

    feed = Feed(
        url=feed_data.url,
        title=feed_data.title,
        interval_seconds=feed_data.interval_seconds,
        per_host_key=per_host_key,
        next_run_at=next_run_at,
    )

    try:
        db.add(feed)
        await db.commit()
        await db.refresh(feed)

        # Enqueue initial fetch job by publishing to Redis
        redis = await get_redis()
        job_data = {
            "job_id": str(uuid.uuid4()),
            "feed_id": str(feed.id),
            "scheduled_at": next_run_at.isoformat(),
        }
        await redis.lpush("rss:jobs", str(job_data))

        return feed
    except Exception as e:
        await db.rollback()
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed URL already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feed",
        )


@router.patch("/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: uuid.UUID, feed_update: FeedUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a feed's properties."""
    # Get the existing feed
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Update only the provided fields
    update_data = feed_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feed, field, value)

    try:
        await db.commit()
        await db.refresh(feed)
        return feed
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feed",
        )


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(feed_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a feed."""
    # First, get the feed to check if it exists
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    try:
        # Delete the feed using ORM to trigger cascade deletes
        await db.delete(feed)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feed",
        )


# Category management endpoints for feeds
@router.get("/{feed_id}/categories", response_model=List[dict])
async def get_feed_categories(feed_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all categories for a feed."""
    from ..models import Category
    from ..models.category import category_feed

    # Check if feed exists
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Get categories for feed
    categories_stmt = (
        select(Category)
        .select_from(category_feed)
        .join(Category, category_feed.c.category_id == Category.id)
        .where(category_feed.c.feed_id == feed_id)
        .order_by(Category.order.asc(), Category.name.asc())
    )
    categories_result = await db.execute(categories_stmt)
    categories = categories_result.scalars().all()

    return [
        {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
            "color": category.color,
            "order": category.order,
        }
        for category in categories
    ]


@router.post("/{feed_id}/categories", response_model=dict)
async def add_feed_to_category(
    feed_id: uuid.UUID, category_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Add a feed to a category."""
    from sqlalchemy import and_

    from ..models import Category
    from ..models.category import category_feed

    # Check if feed exists
    feed_stmt = select(Feed).where(Feed.id == feed_id)
    feed_result = await db.execute(feed_stmt)
    feed = feed_result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Check if category exists
    category_stmt = select(Category).where(Category.id == category_id)
    category_result = await db.execute(category_stmt)
    category = category_result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Check if relationship already exists
    existing_stmt = select(category_feed.c.category_id).where(
        and_(
            category_feed.c.category_id == category_id,
            category_feed.c.feed_id == feed_id,
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        return {
            "message": "Feed is already in this category",
            "category_name": category.name,
            "feed_title": feed.title or feed.url,
        }

    try:
        # Insert new relationship
        insert_stmt = category_feed.insert().values(
            category_id=category_id,
            feed_id=feed_id,
            created_at=datetime.utcnow().isoformat(),
        )
        await db.execute(insert_stmt)
        await db.commit()

        return {
            "message": "Successfully added feed to category",
            "category_name": category.name,
            "feed_title": feed.title or feed.url,
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add feed to category",
        )


@router.delete("/{feed_id}/categories/{category_id}", response_model=dict)
async def remove_feed_from_category(
    feed_id: uuid.UUID, category_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Remove a feed from a category."""
    from sqlalchemy import and_, delete

    from ..models import Category
    from ..models.category import category_feed

    # Check if feed exists
    feed_stmt = select(Feed).where(Feed.id == feed_id)
    feed_result = await db.execute(feed_stmt)
    feed = feed_result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Check if category exists
    category_stmt = select(Category).where(Category.id == category_id)
    category_result = await db.execute(category_stmt)
    category = category_result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    try:
        # Delete the relationship
        delete_stmt = delete(category_feed).where(
            and_(
                category_feed.c.category_id == category_id,
                category_feed.c.feed_id == feed_id,
            )
        )
        result = await db.execute(delete_stmt)
        await db.commit()

        if result.rowcount == 0:
            return {
                "message": "Feed was not in this category",
                "category_name": category.name,
                "feed_title": feed.title or feed.url,
            }

        return {
            "message": "Successfully removed feed from category",
            "category_name": category.name,
            "feed_title": feed.title or feed.url,
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove feed from category",
        )


@router.put("/{feed_id}/categories", response_model=dict)
async def update_feed_categories(
    feed_id: uuid.UUID,
    categories_update: FeedCategoriesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update all categories for a feed (replace existing with new set)."""
    from sqlalchemy import delete

    from ..models import Category
    from ..models.category import category_feed

    # Check if feed exists
    feed_stmt = select(Feed).where(Feed.id == feed_id)
    feed_result = await db.execute(feed_stmt)
    feed = feed_result.scalar_one_or_none()

    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found"
        )

    # Validate that all provided category IDs exist
    if categories_update.category_ids:
        categories_stmt = select(Category).where(
            Category.id.in_(categories_update.category_ids)
        )
        categories_result = await db.execute(categories_stmt)
        existing_categories = categories_result.scalars().all()
        existing_category_ids = {cat.id for cat in existing_categories}

        missing_ids = set(categories_update.category_ids) - existing_category_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categories not found: {list(missing_ids)}",
            )

    try:
        # Remove all existing category relationships for this feed
        delete_stmt = delete(category_feed).where(category_feed.c.feed_id == feed_id)
        await db.execute(delete_stmt)

        # Add new category relationships
        if categories_update.category_ids:
            insert_values = [
                {
                    "category_id": category_id,
                    "feed_id": feed_id,
                    "created_at": datetime.utcnow().isoformat(),
                }
                for category_id in categories_update.category_ids
            ]
            insert_stmt = category_feed.insert().values(insert_values)
            await db.execute(insert_stmt)

        await db.commit()

        return {
            "message": "Successfully updated feed categories",
            "feed_title": feed.title or feed.url,
            "category_count": len(categories_update.category_ids),
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feed categories",
        )
