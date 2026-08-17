import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "website", name="uq_companies_workspace_website"
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    website = Column(String(255), nullable=False)
    industry = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    product_summary = Column(String(1000), nullable=False)
    research_completed = Column(Boolean, default=False, nullable=False)

    workspace = relationship("Workspace", back_populates="companies")
    leads = relationship("Lead", back_populates="company_record")
