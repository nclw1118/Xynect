import uuid

from sqlalchemy import Column, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(256), nullable=False, unique=True)

    supported_states = Column(JSONB, nullable=False, default=list)
    supported_material_types = Column(JSONB, nullable=False, default=list)
    supported_opening_types = Column(JSONB, nullable=False, default=list)
    supported_window_materials = Column(JSONB, nullable=False, default=list)
    supported_glass_types = Column(JSONB, nullable=False, default=list)

    min_width = Column(Float, nullable=True)
    max_width = Column(Float, nullable=True)
    min_height = Column(Float, nullable=True)
    max_height = Column(Float, nullable=True)

    base_unit_price = Column(Float, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    reliability_score = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)

    recommendations = relationship("Recommendation", back_populates="supplier")
