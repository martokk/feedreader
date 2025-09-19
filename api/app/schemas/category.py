import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order: Optional[int] = Field(0, ge=0)

    @validator("name")
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Category name cannot be empty or only whitespace")
        return v.strip()

    @validator("color")
    def validate_color(cls, v):
        if v is not None and not v.startswith("#"):
            raise ValueError("Color must be in hex format starting with #")
        return v


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order: Optional[int] = Field(None, ge=0)

    @validator("name")
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Category name cannot be empty or only whitespace")
        return v.strip() if v is not None else v

    @validator("color")
    def validate_color(cls, v):
        if v is not None and not v.startswith("#"):
            raise ValueError("Color must be in hex format starting with #")
        return v


class CategoryStats(BaseModel):
    """Schema for category statistics."""

    category_id: uuid.UUID
    feed_count: int
    total_items: int
    unread_items: int
    last_updated: Optional[datetime]


class CategoryItemsRequest(BaseModel):
    """Schema for filtering and pagination of category items."""

    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)
    read_status: Optional[str] = Field(None, pattern=r"^(read|unread)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class BulkFeedAssignment(BaseModel):
    """Schema for bulk feed assignment to categories."""

    feed_ids: List[uuid.UUID] = Field(..., min_items=1)


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    color: Optional[str]
    order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryWithFeeds(CategoryResponse):
    """Category response with associated feeds."""

    feeds: List["FeedResponse"] = []

    class Config:
        from_attributes = True


class CategoryWithStats(CategoryResponse):
    """Category response with statistics."""

    feed_count: int
    total_items: int
    unread_items: int

    class Config:
        from_attributes = True


# Forward reference resolution
from .feed import FeedResponse

CategoryWithFeeds.model_rebuild()
