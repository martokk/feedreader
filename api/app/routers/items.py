import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..models import Item, ReadState
from ..schemas.item import ItemDetail, ItemResponse
from ..schemas.read_state import ReadStateUpdate

router = APIRouter(prefix="/feeds", tags=["items"])


@router.get("/{feed_id}/items", response_model=List[ItemResponse])
async def get_feed_items(
    feed_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = Query(False),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get items for a specific feed."""
    # Build query
    stmt = select(Item).where(Item.feed_id == feed_id)

    # Add date filters
    if since:
        stmt = stmt.where(Item.published_at >= since)
    if until:
        stmt = stmt.where(Item.published_at <= until)

    # Join with read_state to get read status
    stmt = stmt.outerjoin(ReadState).options(selectinload(Item.read_state))

    # Filter for unread only if requested
    if unread_only:
        stmt = stmt.where(or_(ReadState.read_at.is_(None), ReadState.item_id.is_(None)))

    # Order and paginate
    stmt = stmt.order_by(Item.published_at.desc().nullslast(), Item.created_at.desc())
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    items = result.scalars().all()

    # Convert to response format
    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "feed_id": item.feed_id,
            "title": item.title,
            "url": item.url,
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


@router.get("/items/{item_id}", response_model=ItemDetail)
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full item details."""
    stmt = select(Item).where(Item.id == item_id).options(selectinload(Item.read_state))
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    item_dict = {
        "id": item.id,
        "feed_id": item.feed_id,
        "title": item.title,
        "url": item.url,
        "content_html": item.content_html,
        "content_text": item.content_text,
        "published_at": item.published_at,
        "fetched_at": item.fetched_at,
        "created_at": item.created_at,
        "is_read": item.read_state.read_at is not None if item.read_state else False,
        "starred": item.read_state.starred if item.read_state else False,
    }

    return ItemDetail(**item_dict)


@router.post("/items/{item_id}/read", status_code=status.HTTP_200_OK)
async def update_read_status(
    item_id: uuid.UUID, read_update: ReadStateUpdate, db: AsyncSession = Depends(get_db)
):
    """Update read status of an item."""
    # Check if item exists
    stmt = select(Item).where(Item.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    # Get or create read state
    stmt = select(ReadState).where(ReadState.item_id == item_id)
    result = await db.execute(stmt)
    read_state = result.scalar_one_or_none()

    if not read_state:
        read_state = ReadState(item_id=item_id)
        db.add(read_state)

        # Update read status
    if read_update.read is not None:
        if read_update.read:
            read_state.read_at = datetime.utcnow()
        else:
            read_state.read_at = None

    # Update starred status
    if read_update.starred is not None:
        read_state.starred = read_update.starred

    await db.commit()

    return {"status": "updated"}
