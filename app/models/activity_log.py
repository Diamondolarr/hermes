from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from app.db.base import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=True, index=True)
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=True, index=True
    )
    event_type = Column(String(100), nullable=False, index=True)
    message = Column(String(1000), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
