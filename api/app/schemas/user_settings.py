"""User settings schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserSettingsBase(BaseModel):
    """Base user settings schema."""
    theme: str = "system"
    mark_read_on_scroll: bool = True


class UserSettingsCreate(UserSettingsBase):
    """Schema for creating user settings."""
    theme: Optional[str] = "system"
    mark_read_on_scroll: Optional[bool] = True


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings."""
    theme: Optional[str] = None
    mark_read_on_scroll: Optional[bool] = None


class UserSettings(UserSettingsBase):
    """Schema for user settings response."""
    id: str
    user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True