from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class GeneratedEmail(Base):
    __tablename__ = "generated_emails"
    __table_args__ = (
        UniqueConstraint(
            "lead_id", "campaign_id", name="uq_generated_emails_lead_campaign"
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    subject = Column(String(255), nullable=False)
    body = Column(String(5000), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="generated_emails")
    campaign = relationship("Campaign", back_populates="generated_emails")
