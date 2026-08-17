from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_leads_workspace_email"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=False, index=True)
    company = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    website = Column(String(255), nullable=False)
    linkedin_url = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="NEW")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace", back_populates="leads")
    company_record = relationship("Company", back_populates="leads")
    insight = relationship(
        "LeadInsight", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )
    sales_insight = relationship(
        "SalesInsight",
        back_populates="lead",
        uselist=False,
        cascade="all, delete-orphan",
    )
    generated_emails = relationship(
        "GeneratedEmail", back_populates="lead", cascade="all, delete-orphan"
    )
    followups = relationship(
        "Followup", back_populates="lead", cascade="all, delete-orphan"
    )
    scheduled_emails = relationship(
        "ScheduledEmail", back_populates="lead", cascade="all, delete-orphan"
    )
    sent_emails = relationship(
        "SentEmail", back_populates="lead", cascade="all, delete-orphan"
    )
    email_replies = relationship(
        "EmailReply", back_populates="lead", cascade="all, delete-orphan"
    )
    meeting = relationship(
        "Meeting", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )
    notes = relationship("Note", back_populates="lead", cascade="all, delete-orphan")
    reply_classifications = relationship(
        "ReplyClassification",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    generated_replies = relationship(
        "GeneratedReply",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    automation_rule_executions = relationship(
        "AutomationRuleExecution",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    conversation_memories = relationship(
        "ConversationMemory",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
