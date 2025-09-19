import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..models import Category, Feed, Item, ReadState
from ..models.category import category_feed
from ..schemas.category import (
    BulkFeedAssignment,
    CategoryCreate,
    CategoryResponse,
    CategoryStats,
    CategoryUpdate,
    CategoryWithFeeds,
    CategoryWithStats,
)
from ..schemas.feed import FeedResponse
from ..schemas.item import ItemResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    skip: int = 0,
    limit: int = 100,
    order_by: str = Query("order", pattern="^(order|name|created_at)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get all categories with optional ordering."""
    order_column = getattr(Category, order_by)
    stmt = (
        select(Category)
        .offset(skip)
        .limit(limit)
        .order_by(order_column.asc() if order_by == "order" else order_column.desc())
    )
    result = await db.execute(stmt)
    categories = result.scalars().all()
    return categories


@router.get("/with-stats", response_model=List[CategoryWithStats])
async def get_categories_with_stats(
    skip: int = 0,
    limit: int = 100,
    order_by: str = Query("order", pattern="^(order|name|created_at)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get all categories with statistics."""
    order_column = getattr(Category, order_by)

    # Get categories first (simplified approach for now)
    stmt = (
        select(Category)
        .offset(skip)
        .limit(limit)
        .order_by(order_column.asc() if order_by == "order" else order_column.desc())
    )

    result = await db.execute(stmt)
    categories = result.scalars().all()

    categories_with_stats = []
    for category in categories:
        # For now, return zero stats - can be optimized later
        categories_with_stats.append(
            CategoryWithStats(
                id=category.id,
                name=category.name,
                description=category.description,
                color=category.color,
                order=category.order,
                created_at=category.created_at,
                updated_at=category.updated_at,
                feed_count=0,
                total_items=0,
                unread_items=0,
            )
        )

    return categories_with_stats


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single category by ID."""
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    return category


@router.get("/{category_id}/with-feeds", response_model=CategoryWithFeeds)
async def get_category_with_feeds(
    category_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get a category with its associated feeds."""
    stmt = (
        select(Category)
        .options(selectinload(Category.feeds))
        .where(Category.id == category_id)
    )
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    return category


@router.get("/{category_id}/stats", response_model=CategoryStats)
async def get_category_stats(
    category_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific category."""
    # Check if category exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Get feed count
    feed_count_stmt = select(func.count(category_feed.c.feed_id)).where(
        category_feed.c.category_id == category_id
    )
    feed_count_result = await db.execute(feed_count_stmt)
    feed_count = feed_count_result.scalar() or 0

    # Get total items count
    total_items_stmt = (
        select(func.count(Item.id))
        .select_from(category_feed)
        .join(Feed, category_feed.c.feed_id == Feed.id)
        .join(Item, Feed.id == Item.feed_id)
        .where(category_feed.c.category_id == category_id)
    )
    total_items_result = await db.execute(total_items_stmt)
    total_items = total_items_result.scalar() or 0

    # Get unread items count
    unread_items_stmt = (
        select(func.count(Item.id))
        .select_from(category_feed)
        .join(Feed, category_feed.c.feed_id == Feed.id)
        .join(Item, Feed.id == Item.feed_id)
        .outerjoin(ReadState, ReadState.item_id == Item.id)
        .where(category_feed.c.category_id == category_id)
        .where(or_(ReadState.read_at.is_(None), ReadState.item_id.is_(None)))
    )
    unread_items_result = await db.execute(unread_items_stmt)
    unread_items = unread_items_result.scalar() or 0

    # Get last updated timestamp (latest item fetched_at)
    last_updated_stmt = (
        select(func.max(Item.fetched_at))
        .select_from(category_feed)
        .join(Feed, category_feed.c.feed_id == Feed.id)
        .join(Item, Feed.id == Item.feed_id)
        .where(category_feed.c.category_id == category_id)
    )
    last_updated_result = await db.execute(last_updated_stmt)
    last_updated = last_updated_result.scalar()

    return CategoryStats(
        category_id=category_id,
        feed_count=feed_count,
        total_items=total_items,
        unread_items=unread_items,
        last_updated=last_updated,
    )


@router.get("/{category_id}/feeds", response_model=List[FeedResponse])
async def get_category_feeds(
    category_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get all feeds in a category."""
    # Check if category exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Get feeds in category
    feeds_stmt = (
        select(Feed)
        .select_from(category_feed)
        .join(Feed, category_feed.c.feed_id == Feed.id)
        .where(category_feed.c.category_id == category_id)
        .offset(skip)
        .limit(limit)
        .order_by(Feed.title.asc())
    )
    feeds_result = await db.execute(feeds_stmt)
    feeds = feeds_result.scalars().all()

    return feeds


@router.get("/{category_id}/items", response_model=List[ItemResponse])
async def get_category_items(
    category_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    read_status: str = Query(None, pattern=r"^(read|unread)$"),
    date_from: datetime = None,
    date_to: datetime = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all items from feeds in a category with filtering and pagination."""
    # Check if category exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

        # Build items query
    items_stmt = (
        select(Item)
        .select_from(category_feed)
        .join(Feed, category_feed.c.feed_id == Feed.id)
        .join(Item, Feed.id == Item.feed_id)
        .where(category_feed.c.category_id == category_id)
    )

    # Apply filters
    if read_status == "read":
        items_stmt = items_stmt.outerjoin(
            ReadState, ReadState.item_id == Item.id
        ).where(ReadState.read_at.is_not(None))
    elif read_status == "unread":
        items_stmt = items_stmt.outerjoin(
            ReadState, ReadState.item_id == Item.id
        ).where(or_(ReadState.read_at.is_(None), ReadState.item_id.is_(None)))

    if date_from:
        items_stmt = items_stmt.where(Item.published_at >= date_from)

    if date_to:
        items_stmt = items_stmt.where(Item.published_at <= date_to)

    # Add pagination and ordering
    items_stmt = (
        items_stmt.offset(skip)
        .limit(limit)
        .order_by(Item.published_at.desc().nulls_last(), Item.created_at.desc())
    )

    # Execute query and load read_state relationships separately
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()

    # Load read_state for all items
    if items:
        item_ids = [item.id for item in items]
        read_states_stmt = select(ReadState).where(ReadState.item_id.in_(item_ids))
        read_states_result = await db.execute(read_states_stmt)
        read_states = read_states_result.scalars().all()

        # Create a mapping of item_id to read_state
        read_state_map = {rs.item_id: rs for rs in read_states}

        # Assign read_state to items
        for item in items:
            item.read_state = read_state_map.get(item.id)

    # Convert to response format
    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "feed_id": item.feed_id,
            "title": item.title,
            "url": item.url,
            "content_text": item.content_text,
            "published_at": item.published_at,
            "fetched_at": item.fetched_at,
            "created_at": item.created_at,
            "is_read": item.read_state.read_at is not None
            if item.read_state
            else False,
            "starred": item.read_state.starred if item.read_state else False,
        }
        response_items.append(ItemResponse(**item_dict))

    return response_items


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new category."""
    category = Category(
        name=category_data.name,
        description=category_data.description,
        color=category_data.color,
        order=category_data.order,
    )

    try:
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category
    except Exception as e:
        await db.rollback()
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category name already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category",
        )


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    category_update: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a category's properties."""
    # Get the existing category
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Update only the provided fields
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    try:
        await db.commit()
        await db.refresh(category)
        return category
    except Exception as e:
        await db.rollback()
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category name already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category",
        )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a category."""
    # First, get the category to check if it exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    try:
        # Delete the category (cascade will handle category_feed relationships)
        await db.delete(category)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category",
        )


@router.post("/{category_id}/feeds", response_model=dict)
async def add_feeds_to_category(
    category_id: uuid.UUID,
    bulk_assignment: BulkFeedAssignment,
    db: AsyncSession = Depends(get_db),
):
    """Add multiple feeds to a category."""
    # Check if category exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Check if all feeds exist
    feeds_stmt = select(Feed).where(Feed.id.in_(bulk_assignment.feed_ids))
    feeds_result = await db.execute(feeds_stmt)
    existing_feeds = feeds_result.scalars().all()
    existing_feed_ids = {feed.id for feed in existing_feeds}

    missing_feed_ids = set(bulk_assignment.feed_ids) - existing_feed_ids
    if missing_feed_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feeds not found: {list(missing_feed_ids)}",
        )

    # Check for existing relationships to avoid duplicates
    existing_relationships_stmt = select(category_feed.c.feed_id).where(
        and_(
            category_feed.c.category_id == category_id,
            category_feed.c.feed_id.in_(bulk_assignment.feed_ids),
        )
    )
    existing_relationships_result = await db.execute(existing_relationships_stmt)
    existing_relationship_feed_ids = {
        row[0] for row in existing_relationships_result.all()
    }

    # Only add feeds that aren't already in the category
    new_feed_ids = set(bulk_assignment.feed_ids) - existing_relationship_feed_ids

    if not new_feed_ids:
        return {
            "message": "All feeds are already in the category",
            "added_count": 0,
            "skipped_count": len(bulk_assignment.feed_ids),
        }

    try:
        # Insert new relationships
        values = [
            {
                "category_id": category_id,
                "feed_id": feed_id,
                "created_at": datetime.utcnow().isoformat(),
            }
            for feed_id in new_feed_ids
        ]

        insert_stmt = category_feed.insert().values(values)
        await db.execute(insert_stmt)
        await db.commit()

        return {
            "message": f"Successfully added {len(new_feed_ids)} feeds to category",
            "added_count": len(new_feed_ids),
            "skipped_count": len(existing_relationship_feed_ids),
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add feeds to category",
        )


@router.delete("/{category_id}/feeds", response_model=dict)
async def remove_feeds_from_category(
    category_id: uuid.UUID,
    bulk_assignment: BulkFeedAssignment,
    db: AsyncSession = Depends(get_db),
):
    """Remove multiple feeds from a category."""
    # Check if category exists
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    try:
        # Delete the relationships
        delete_stmt = delete(category_feed).where(
            and_(
                category_feed.c.category_id == category_id,
                category_feed.c.feed_id.in_(bulk_assignment.feed_ids),
            )
        )
        result = await db.execute(delete_stmt)
        await db.commit()

        removed_count = result.rowcount

        return {
            "message": f"Successfully removed {removed_count} feeds from category",
            "removed_count": removed_count,
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove feeds from category",
        )
