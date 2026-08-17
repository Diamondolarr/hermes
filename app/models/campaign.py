from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    target_icp = Column(String(255), nullable=False)
    message_tone = Column(String(255), nullable=False)
    cta_type = Column(String(255), nullable=False)
    daily_send_limit = Column(Integer, nullable=False, default=50)
    send_time_window_start = Column(String(5), nullable=False, default="09:00")
    send_time_window_end = Column(String(5), nullable=False, default="17:00")
    send_timezone = Column(String(64), nullable=False, default="UTC")
    followup_delay_days = Column(Integer, nullable=False, default=3)
    status = Column(String(50), nullable=False, default="DRAFT")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace", back_populates="campaigns")
    generated_emails = relationship(
        "GeneratedEmail", back_populates="campaign", cascade="all, delete-orphan"
    )
    followups = relationship(
        "Followup", back_populates="campaign", cascade="all, delete-orphan"
    )
    scheduled_emails = relationship(
        "ScheduledEmail", back_populates="campaign", cascade="all, delete-orphan"
    )
    sent_emails = relationship(
        "SentEmail", back_populates="campaign", cascade="all, delete-orphan"
    )
    automation_rules = relationship(
        "AutomationRule", back_populates="campaign", cascade="all, delete-orphan"
    )
    automation_rule_executions = relationship(
        "AutomationRuleExecution",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    insight = relationship(
        "CampaignInsight",
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan",
    )
