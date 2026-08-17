from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    human_approval_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship(
        "User", back_populates="workspace", foreign_keys="User.workspace_id"
    )
    email_accounts = relationship("EmailAccount", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="workspace", cascade="all, delete-orphan")
    automation_rules = relationship(
        "AutomationRule", back_populates="workspace", cascade="all, delete-orphan"
    )
    companies = relationship(
        "Company", back_populates="workspace", cascade="all, delete-orphan"
    )
    leads = relationship("Lead", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="workspace", cascade="all, delete-orphan")
    conversation_memories = relationship(
        "ConversationMemory",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    notifications = relationship(
        "Notification", back_populates="workspace", cascade="all, delete-orphan"
    )
