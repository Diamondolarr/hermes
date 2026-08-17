from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmailReply(Base):
    __tablename__ = "email_replies"
    __table_args__ = (
        UniqueConstraint(
            "email_account_id",
            "message_id",
            name="uq_email_replies_account_message",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    email_account_id = Column(
        String(36), ForeignKey("email_accounts.id"), nullable=False, index=True
    )
    message_id = Column(String(255), nullable=False, index=True)
    thread_id = Column(String(255), nullable=True, index=True)
    reply_body = Column(String(10000), nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    lead = relationship("Lead", back_populates="email_replies")
    email_account = relationship("EmailAccount", back_populates="email_replies")
    classification = relationship(
        "ReplyClassification",
        back_populates="email_reply",
        uselist=False,
        cascade="all, delete-orphan",
    )
    generated_reply = relationship(
        "GeneratedReply",
        back_populates="email_reply",
        uselist=False,
        cascade="all, delete-orphan",
    )
