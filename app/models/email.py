from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    access_token = Column(String(2048), nullable=False)
    refresh_token = Column(String(2048), nullable=False)
    email_address = Column(String(320), nullable=False, index=True)
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace")
    sent_emails = relationship(
        "SentEmail", back_populates="email_account", cascade="all, delete-orphan"
    )
    email_replies = relationship(
        "EmailReply", back_populates="email_account", cascade="all, delete-orphan"
    )
