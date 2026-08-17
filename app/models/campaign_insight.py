from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class CampaignInsight(Base):
    __tablename__ = "campaign_insights"
    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_insights_campaign"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    best_subject_line = Column(String(255), nullable=False)
    best_send_time = Column(String(255), nullable=False)
    best_industry_response = Column(String(255), nullable=False)
    summary = Column(String(1000), nullable=False)
    recommendations = Column(JSON, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    campaign = relationship("Campaign", back_populates="insight")
