from datetime import datetime
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    provider = Column(String(100), nullable=False, index=True)
    feature = Column(String(100), nullable=False, index=True)
    model_name = Column(String(255), nullable=True, index=True)
    request_count = Column(Integer, nullable=False, default=1)
    estimated_input_tokens = Column(Integer, nullable=True)
    estimated_output_tokens = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True, index=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
