from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

# Association table for many-to-many relationship between categories and feeds
category_feed = Table(
    "category_feed",
    Base.metadata,
    Column(
        "category_id",
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "feed_id",
        UUID(as_uuid=True),
        ForeignKey("feeds.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", String, server_default="now()", nullable=False),
    Index("ix_category_feed_category_id", "category_id"),
    Index("ix_category_feed_feed_id", "feed_id"),
)


class Category(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True
    )  # Hex color format #RRGGBB
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    feeds = relationship("Feed", secondary=category_feed, back_populates="categories")

    # Indexes
    __table_args__ = (
        Index("ix_categories_name", "name"),
        Index("ix_categories_order", "order"),
    )
