import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(32), nullable=False, default="uploaded")
    # Valid values: uploaded | processing | review_ready | confirmed | recommendation_ready | error

    uploaded_file_path = Column(String(512), nullable=True)
    uploaded_file_name = Column(String(256), nullable=True)
    uploaded_file_type = Column(String(64), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    )
    error_message = Column(Text, nullable=True)

    project_info = relationship(
        "ProjectInfo",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    window_items = relationship(
        "WindowItem",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    door_items = relationship(
        "DoorItem",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    progress_steps = relationship(
        "ProgressStep",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ProgressStep.order_index",
    )
    recommendations = relationship(
        "Recommendation",
        back_populates="session",
        cascade="all, delete-orphan",
    )
