import enum
import uuid
from datetime import datetime, UTC
from typing import Any, Optional
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.database import Base

class MemoryType(str, enum.Enum):
    SEMANTIC = "SEMANTIC"
    PREFERENCE = "PREFERENCE"
    EPISODIC = "EPISODIC"
    PROCEDURAL = "PROCEDURAL"
    TASK = "TASK"

class TemporalState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    DELETED = "DELETED"

def current_utc_time():
    return datetime.now(UTC)

class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=func.cast('{}', JSONB), nullable=False)
    temporal_state: Mapped[TemporalState] = mapped_column(default=TemporalState.ACTIVE, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False, index=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("memories.id", ondelete="SET NULL"), nullable=True, index=True)

    superseded_by: Mapped[Optional["Memory"]] = relationship("Memory", remote_side=[id], backref="superseded_memories", lazy="selectin")

    __table_args__ = (
        CheckConstraint("importance >= 0.0 AND importance <= 1.0", name="check_importance_range"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="check_confidence_range"),
        Index(
            "ix_memories_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
        Index("ix_memories_tenant_agent_state", "tenant_id", "agent_id", "temporal_state")
    )
