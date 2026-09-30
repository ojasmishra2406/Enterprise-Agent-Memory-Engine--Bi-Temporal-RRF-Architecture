import asyncio
import json
from mcp.server.fastmcp import FastMCP
from app.database import SessionLocal
from app.services.memory_manager import MemoryManager
from app.services.retrieval_service import RetrievalService
from app.schemas import IngestRequest, MessageTurn, SearchRequest
from app.logging_config import setup_logging
import structlog
from app.models import Memory, TemporalState
from sqlalchemy import select

setup_logging()
logger = structlog.get_logger(__name__)

mcp = FastMCP("agent-memory-engine")

@mcp.tool()
async def ingest_conversation(tenant_id: str, agent_id: str, session_id: str, messages: list[dict], metadata: dict = None) -> str:
    """Ingest a conversation and extract salient memory facts."""
    if metadata is None:
        metadata = {}
    req = IngestRequest(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        messages=[MessageTurn.model_validate(m) for m in messages],
        metadata=metadata
    )
    async with SessionLocal() as db:
        manager = MemoryManager(db)
        results = await manager.ingest_transcript(req)
        await db.commit()
        return json.dumps([r.model_dump(mode="json") for r in results])

@mcp.tool()
async def search_memories(tenant_id: str, agent_id: str, query: str, limit: int = 10) -> str:
    """Search for relevant active memories using Hybrid RRF search."""
    req = SearchRequest(tenant_id=tenant_id, agent_id=agent_id, query=query, limit=limit)
    async with SessionLocal() as db:
        service = RetrievalService(db)
        results = await service.hybrid_search(req)
        return json.dumps([r.model_dump(mode="json") for r in results])

@mcp.tool()
async def get_memory_lineage(memory_id: str, tenant_id: str) -> str:
    """Retrieve the full historical lineage of a specific memory."""
    import uuid
    async with SessionLocal() as db:
        manager = MemoryManager(db)
        res = await manager.get_memory_lineage(uuid.UUID(memory_id), tenant_id)
        if not res:
            return json.dumps({"error": "Memory not found"})
        return json.dumps({
            "current_memory": res["current_memory"].id.hex,
            "history_chain": [m.id.hex for m in res["history_chain"]]
        })

@mcp.tool()
async def list_active_memories(tenant_id: str, agent_id: str, memory_type: str = None) -> str:
    """List active memories for an agent."""
    async with SessionLocal() as db:
        stmt = select(Memory).where(Memory.tenant_id == tenant_id, Memory.agent_id == agent_id, Memory.temporal_state == TemporalState.ACTIVE)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        mems = (await db.scalars(stmt)).all()
        return json.dumps([{"id": m.id.hex, "content": m.content, "type": m.memory_type} for m in mems])

if __name__ == "__main__":
    mcp.run(transport="stdio")
