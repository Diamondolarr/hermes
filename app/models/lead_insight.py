from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class LeadInsight(Base):
    __tablename__ = "lead_insights"
    __table_args__ = (UniqueConstraint("lead_id", name="uq_lead_insights_lead_id"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    role_category = Column(String(255), nullable=False)
    possible_pain_points = Column(JSON, nullable=False)
    recommended_sales_angle = Column(String(1000), nullable=False)
    confidence_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    lead = relationship("Lead", back_populates="insight")
