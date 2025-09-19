import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ReadState(Base):
    __tablename__ = "read_state"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), primary_key=True, nullable=False
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    item = relationship("Item", back_populates="read_state")
