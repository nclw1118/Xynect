import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProjectInfo(Base):
    __tablename__ = "project_info"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, unique=True)

    project_name = Column(String(256), nullable=True)
    site_address = Column(String(512), nullable=True)
    city = Column(String(128), nullable=True)
    state = Column(String(64), nullable=True)
    zip_code = Column(String(16), nullable=True)
    detected_file_type = Column(String(64), nullable=True)
    detected_relevant_pages = Column(JSONB, nullable=True)

    session = relationship("Session", back_populates="project_info")
