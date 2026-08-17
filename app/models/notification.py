from datetime import datetime
import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "channel",
            "event_type",
            "resource_type",
            "resource_id",
            name="uq_notifications_user_channel_event_resource",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(String(5000), nullable=False)
    status = Column(String(50), nullable=False, default="DELIVERED")
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    workspace = relationship("Workspace", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
