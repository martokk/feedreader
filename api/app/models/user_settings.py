"""User settings model."""

from sqlalchemy import Boolean, Column, String, DateTime
from sqlalchemy.sql import func

from .base import Base


class UserSettings(Base):
    """User settings model."""
    
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)  # For future user management
    theme = Column(String, nullable=False, default="system")
    mark_read_on_scroll = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())