from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
import uuid
import enum
from app.models import MemoryType, TemporalState

class MessageTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[datetime] = None

class IngestRequest(BaseModel):
    tenant_id: str
    agent_id: str
    session_id: str
    messages: list[MessageTurn]
    metadata: dict[str, Any] = Field(default_factory=dict)

class ExtractedFact(BaseModel):
    content: str
    memory_type: MemoryType
    importance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

class FactExtractionOutput(BaseModel):
    facts: list[ExtractedFact]

class ResolutionAction(str, enum.Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    NONE = "NONE"

class ContradictionDecision(BaseModel):
    action: ResolutionAction
    target_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    updated_content: Optional[str] = None
    reason: str

class MemoryRecordResponse(BaseModel):
    id: uuid.UUID
    tenant_id: str
    agent_id: str
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    source_provenance: dict[str, Any]
    temporal_state: TemporalState
    created_at: datetime
    valid_from: datetime
    valid_to: Optional[datetime]
    superseded_by_id: Optional[uuid.UUID]

class FactResolutionReport(BaseModel):
    extracted_fact: ExtractedFact
    action_taken: ResolutionAction
    memory_id: Optional[uuid.UUID]
    superseded_memory_ids: list[uuid.UUID]
    reason: str

class IngestResponse(BaseModel):
    session_id: str
    processed_count: int
    results: list[FactResolutionReport]

class MemoryLineageResponse(BaseModel):
    current_memory: MemoryRecordResponse
    history_chain: list[MemoryRecordResponse]

class SearchRequest(BaseModel):
    tenant_id: str
    agent_id: str
    query: str
    limit: int = Field(default=10, ge=1, le=50)

class SearchResult(BaseModel):
    memory_id: uuid.UUID
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    rrf_score: float
    final_score: float
