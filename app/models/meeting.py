from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (UniqueConstraint("lead_id", name="uq_meetings_lead"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=True)
    meeting_link = Column(String(1000), nullable=False)
    status = Column(String(50), nullable=False, default="LINK_SENT")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="meeting")
