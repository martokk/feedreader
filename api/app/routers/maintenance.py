"""Maintenance router for dangerous operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.item import Item
from ..models.read_state import ReadState

router = APIRouter()


@router.delete("/items/all", status_code=status.HTTP_200_OK)
async def remove_all_feed_items(db: AsyncSession = Depends(get_db)):
    """Remove all feed items from the database.

    WARNING: This operation is irreversible and will delete all feed items
    and their associated read states. Feeds will appear as if they are being
    scanned for the first time.
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

        return {
            "message": "Successfully removed all feed items",
            "items_deleted": items_deleted,
            "read_states_deleted": read_states_deleted,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove feed items: {str(e)}",
        )
