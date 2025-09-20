import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator


class FeedCreate(BaseModel):
    url: str
    title: Optional[str] = None
    interval_seconds: Optional[int] = 900

    @validator("url")
    def validate_url(cls, v):
        # Basic URL validation
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class FeedUpdate(BaseModel):
    """Schema for updating feed properties."""

    title: Optional[str] = None
    interval_seconds: Optional[int] = None

    @validator("interval_seconds")
    def validate_interval(cls, v):
        if v is not None and v < 60:
            raise ValueError("Interval must be at least 60 seconds")
        return v


class FeedStats(BaseModel):
    """Schema for feed statistics."""

    feed_id: uuid.UUID
    total_items: int
    unread_items: int
    last_fetch_at: Optional[datetime]
    last_fetch_status: Optional[int]
    last_error: Optional[str] = None
    next_run_at: datetime


class FeedValidation(BaseModel):
    """Schema for feed URL validation result."""

    url: str
    is_valid: bool
    feed_title: Optional[str] = None
    error_message: Optional[str] = None


class FeedResponse(BaseModel):
    id: uuid.UUID
    url: str
    title: Optional[str]
    last_fetch_at: Optional[datetime]
    last_status: Optional[int]
    last_error: Optional[str] = None
    next_run_at: datetime
    interval_seconds: int
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0

    class Config:
        from_attributes = True


class FeedWithCategories(FeedResponse):
    """Feed response with associated categories."""

    categories: List["CategoryResponse"] = []
    unread_count: int = 0

    class Config:
        from_attributes = True


# Forward reference resolution
from .category import CategoryResponse

FeedWithCategories.model_rebuild()
