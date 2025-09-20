import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Item(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "items"

    feed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feeds.id"), nullable=False
    )
    guid: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    feed = relationship("Feed", back_populates="items")
    read_state = relationship("ReadState", back_populates="item", uselist=False)

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_items_feed_guid"),
        Index("ix_items_published_at", "published_at"),
        Index("ix_items_created_at", "created_at"),
        Index("ix_items_feed_id", "feed_id"),
    )
