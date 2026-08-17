from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    company_name = Column(String(255), nullable=False)
    company_website = Column(String(255), nullable=False)
    product_description = Column(String(1000), nullable=False)
    industry = Column(String(255), nullable=False)
    target_market = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace")


class IdealCustomerProfile(Base):
    __tablename__ = "ideal_customer_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    target_industry = Column(String(255), nullable=False)
    target_company_size = Column(String(255), nullable=False)
    target_roles = Column(JSON, nullable=False)
    target_region = Column(String(255), nullable=False)
    pain_points = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace")
