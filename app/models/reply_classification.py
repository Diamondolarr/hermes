from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReplyClassification(Base):
    __tablename__ = "reply_classifications"
    __table_args__ = (
        UniqueConstraint(
            "email_reply_id", name="uq_reply_classifications_email_reply"
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_reply_id = Column(
        String(36), ForeignKey("email_replies.id"), nullable=False, index=True
    )
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)
    reason = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    email_reply = relationship("EmailReply", back_populates="classification")
    lead = relationship("Lead", back_populates="reply_classifications")
