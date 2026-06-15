import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DoorItem(Base):
    __tablename__ = "door_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)

    tag = Column(String(64), nullable=True)
    material_type = Column(String(64), nullable=False, default="Door")
    width = Column(String(64), nullable=True)
    height = Column(String(64), nullable=True)
    area = Column(String(64), nullable=True)
    quantity = Column(String(32), nullable=True)
    opening_type = Column(String(128), nullable=True)
    material = Column(String(128), nullable=True)
    fire_rating = Column(String(64), nullable=True)
    self_closing = Column(String(32), nullable=True)
    glass_type = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)

    # Stores the original AI/parser extraction for each field (shape: {field: {original_value, ...}})
    original_extraction = Column(JSONB, nullable=True)
    # Stores per-field edit tracking (shape: {field: {original_value, current_value, edited_by_user}})
    user_edits = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    session = relationship("Session", back_populates="door_items")
