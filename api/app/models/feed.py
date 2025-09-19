from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Feed(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "feeds"

    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_modified: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fetch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    per_host_key: Mapped[str] = mapped_column(String(256), nullable=False)

    # Relationships
    items = relationship("Item", back_populates="feed", cascade="all, delete-orphan")
    fetch_logs = relationship(
        "FetchLog", back_populates="feed", cascade="all, delete-orphan"
    )
    categories = relationship(
        "Category", secondary="category_feed", back_populates="feeds"
    )

    # Indexes
    __table_args__ = (
        Index("ix_feeds_next_run_at", "next_run_at"),
        Index("ix_feeds_per_host_key", "per_host_key"),
    )
