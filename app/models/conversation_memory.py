from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.types import EmbeddingType


class ConversationMemory(Base):
    __tablename__ = "conversation_memories"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_conversation_memories_source",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    content = Column(String(10000), nullable=False)
    embedding = Column(EmbeddingType(1536), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    workspace = relationship("Workspace", back_populates="conversation_memories")
    lead = relationship("Lead", back_populates="conversation_memories")
