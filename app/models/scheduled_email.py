from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"
    __table_args__ = (
        UniqueConstraint(
            "lead_id",
            "campaign_id",
            "step_number",
            name="uq_scheduled_emails_step",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    step_number = Column(Integer, nullable=False)
    email_type = Column(String(20), nullable=False)
    draft_subject = Column(String(255), nullable=True)
    draft_body = Column(String(5000), nullable=True)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    approval_status = Column(String(50), nullable=False, default="APPROVED", index=True)
    approved_by_user_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by_user_id = Column(String(36), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="scheduled_emails")
    campaign = relationship("Campaign", back_populates="scheduled_emails")
