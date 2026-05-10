import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    window_item_id = Column(String(36), ForeignKey("window_items.id"), nullable=False)
    supplier_id = Column(String(36), ForeignKey("suppliers.id"), nullable=False)

    tag = Column(String(64), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    estimated_total = Column(Float, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    match_score = Column(Float, nullable=False)
    match_reason = Column(Text, nullable=True)
    risk_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session = relationship("Session", back_populates="recommendations")
    window_item = relationship("WindowItem", back_populates="recommendations")
    supplier = relationship("Supplier", back_populates="recommendations")
