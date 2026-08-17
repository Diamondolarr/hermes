from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class GeneratedReply(Base):
    __tablename__ = "generated_replies"
    __table_args__ = (
        UniqueConstraint("email_reply_id", name="uq_generated_replies_email_reply"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_reply_id = Column(
        String(36), ForeignKey("email_replies.id"), nullable=False, index=True
    )
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(String(5000), nullable=False)
    reply_goal = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    email_reply = relationship("EmailReply", back_populates="generated_reply")
    lead = relationship("Lead", back_populates="generated_replies")
