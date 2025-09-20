import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ItemResponse(BaseModel):
    id: uuid.UUID
    feed_id: uuid.UUID
    title: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    content_text: Optional[str]
    published_at: Optional[datetime]
    fetched_at: datetime
    created_at: datetime
    is_read: bool
    starred: bool

    class Config:
        from_attributes = True


class ItemDetail(BaseModel):
    id: uuid.UUID
    feed_id: uuid.UUID
    title: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    content_html: Optional[str]
    content_text: Optional[str]
    published_at: Optional[datetime]
    fetched_at: datetime
    created_at: datetime
    is_read: bool
    starred: bool

    class Config:
        from_attributes = True
