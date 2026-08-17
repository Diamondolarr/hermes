from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=True, index=True
    )
    name = Column(String(255), nullable=False)
    trigger_type = Column(String(100), nullable=False)
    delay_days = Column(Integer, nullable=False)
    action_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace", back_populates="automation_rules")
    campaign = relationship("Campaign", back_populates="automation_rules")
    executions = relationship(
        "AutomationRuleExecution",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class AutomationRuleExecution(Base):
    __tablename__ = "automation_rule_executions"
    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "lead_id",
            "campaign_id",
            "target_step_number",
            name="uq_automation_rule_execution_target_step",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(
        String(36), ForeignKey("automation_rules.id"), nullable=False, index=True
    )
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    target_step_number = Column(Integer, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), nullable=False)

    rule = relationship("AutomationRule", back_populates="executions")
    lead = relationship("Lead", back_populates="automation_rule_executions")
    campaign = relationship("Campaign", back_populates="automation_rule_executions")
