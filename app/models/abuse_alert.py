from datetime import datetime
import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint

from app.db.base import Base


class AbuseAlert(Base):
    __tablename__ = "abuse_alerts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_abuse_alerts_dedupe_key"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="OPEN", index=True)
    dedupe_key = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
