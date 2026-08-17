from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class SentEmail(Base):
    __tablename__ = "sent_emails"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    email_account_id = Column(
        String(36), ForeignKey("email_accounts.id"), nullable=True, index=True
    )
    message_id = Column(String(255), nullable=True)
    thread_id = Column(String(255), nullable=True, index=True)
    email_subject = Column(String(255), nullable=True)
    email_body = Column(String(5000), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), nullable=False)

    lead = relationship("Lead", back_populates="sent_emails")
    campaign = relationship("Campaign", back_populates="sent_emails")
    email_account = relationship("EmailAccount", back_populates="sent_emails")
