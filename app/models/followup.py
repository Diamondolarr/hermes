from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Followup(Base):
    __tablename__ = "followups"
    __table_args__ = (
        UniqueConstraint("lead_id", "campaign_id", "step_number", name="uq_followups_step"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    step_number = Column(Integer, nullable=False)
    email_subject = Column(String(255), nullable=False)
    email_body = Column(String(5000), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)

    lead = relationship("Lead", back_populates="followups")
    campaign = relationship("Campaign", back_populates="followups")
