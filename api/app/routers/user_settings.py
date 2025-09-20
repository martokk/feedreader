"""User settings router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.user_settings import UserSettings as UserSettingsModel
from ..schemas.user_settings import UserSettings, UserSettingsCreate, UserSettingsUpdate

router = APIRouter()


@router.get("/settings", response_model=UserSettings, tags=["settings"])
async def get_user_settings(db: AsyncSession = Depends(get_db)):
    """Get user settings (returns first/default settings since no user management yet)."""
    stmt = select(UserSettingsModel).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings if none exist
        settings = UserSettingsModel(
            id=str(uuid.uuid4()),
            theme="system",
            mark_read_on_scroll=True,
            hide_read_items=False,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.post("/settings", response_model=UserSettings, tags=["settings"])
async def create_user_settings(
    settings_data: UserSettingsCreate, db: AsyncSession = Depends(get_db)
):
    """Create user settings."""
    # Check if settings already exist (since we don't have user management yet)
    stmt = select(UserSettingsModel).limit(1)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Settings already exist")

    settings = UserSettingsModel(
        id=str(uuid.uuid4()),
        theme=settings_data.theme,
        mark_read_on_scroll=settings_data.mark_read_on_scroll,
        hide_read_items=settings_data.hide_read_items,
    )
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


@router.patch("/settings", response_model=UserSettings, tags=["settings"])
async def update_user_settings(
    settings_data: UserSettingsUpdate, db: AsyncSession = Depends(get_db)
):
    """Update user settings."""
    stmt = select(UserSettingsModel).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings:
        # Create settings if none exist
        settings = UserSettingsModel(
            id=str(uuid.uuid4()),
            theme=settings_data.theme or "system",
            mark_read_on_scroll=settings_data.mark_read_on_scroll
            if settings_data.mark_read_on_scroll is not None
            else True,
            hide_read_items=settings_data.hide_read_items
            if settings_data.hide_read_items is not None
            else False,
        )
        db.add(settings)
    else:
        # Update existing settings
        if settings_data.theme is not None:
            settings.theme = settings_data.theme
        if settings_data.mark_read_on_scroll is not None:
            settings.mark_read_on_scroll = settings_data.mark_read_on_scroll
        if settings_data.hide_read_items is not None:
            settings.hide_read_items = settings_data.hide_read_items

    await db.commit()
    await db.refresh(settings)
    return settings
