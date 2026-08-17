from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class SalesInsight(Base):
    __tablename__ = "sales_insights"
    __table_args__ = (UniqueConstraint("lead_id", name="uq_sales_insights_lead_id"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    sales_angle = Column(String(1000), nullable=False)
    value_proposition = Column(String(1000), nullable=False)
    personalization_notes = Column(String(2000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    lead = relationship("Lead", back_populates="sales_insight")
