import asyncio
import json
import httpx
import sys
import logging
from mcp.server.fastmcp import FastMCP
from app.database import SessionLocal
from app.services.memory_manager import MemoryManager
from app.services.retrieval_service import RetrievalService
from app.schemas import IngestRequest, MessageTurn, SearchRequest
from app.models import Memory, TemporalState
from sqlalchemy import select

# Configure standard logging to ONLY go to stderr
# We must do this before importing our internal app modules
# to avoid them setting up stdout loggers that corrupt MCP
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")

# Re-configure structlog to use standard logging which goes to stderr
import structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)
logger = structlog.get_logger(__name__)

mcp = FastMCP("agent-memory-engine")

@mcp.tool()
async def ingest_conversation(tenant_id: str, agent_id: str, session_id: str, messages: list[dict], metadata: dict = None) -> str:
    """Ingest a conversation and extract salient memory facts."""
    if metadata is None:
        metadata = {}
    
    try:
        req = IngestRequest(
            agent_id=agent_id,
            session_id=session_id,
            messages=[MessageTurn.model_validate(m) for m in messages],
            metadata=metadata
        )
        async with SessionLocal() as db:
            manager = MemoryManager(db)
            results = await manager.ingest_transcript(req, tenant_id)
            await db.commit()
            return json.dumps([r.model_dump(mode="json") for r in results])
    except httpx.ConnectError as e:
        logger.error("llm_connection_error", error=str(e))
        return f"Error: Unable to connect to the LLM service. Please ensure Ollama is running. Details: {str(e)}"
    except Exception as e:
        logger.error("ingest_error", error=str(e))
        return f"Error: Failed to ingest conversation. Details: {str(e)}"

@mcp.tool()
async def search_memories(tenant_id: str, agent_id: str, query: str, limit: int = 10) -> str:
    """Search for relevant active memories using Hybrid RRF search."""
    try:
        req = SearchRequest(agent_id=agent_id, query=query, limit=limit)
        async with SessionLocal() as db:
            service = RetrievalService(db)
            results = await service.hybrid_search(req, tenant_id)
            return json.dumps([r.model_dump(mode="json") for r in results])
    except httpx.ConnectError as e:
        return f"Error: Unable to connect to the LLM service for embedding generation. Details: {str(e)}"
    except Exception as e:
        return f"Error: Search failed. Details: {str(e)}"

@mcp.tool()
async def get_memory_lineage(memory_id: str, tenant_id: str) -> str:
    """Retrieve the full historical lineage of a specific memory."""
    import uuid
    try:
        async with SessionLocal() as db:
            manager = MemoryManager(db)
            res = await manager.get_memory_lineage(uuid.UUID(memory_id), tenant_id)
            if not res:
                return json.dumps({"error": "Memory not found"})
            return json.dumps({
                "current_memory": res["current_memory"].id.hex,
                "history_chain": [m.id.hex for m in res["history_chain"]]
            })
    except Exception as e:
        return f"Error: Lineage retrieval failed. Details: {str(e)}"

@mcp.tool()
async def list_active_memories(tenant_id: str, agent_id: str, memory_type: str = None) -> str:
    """List active memories for an agent."""
    try:
        async with SessionLocal() as db:
            stmt = select(Memory).where(Memory.tenant_id == tenant_id, Memory.agent_id == agent_id, Memory.temporal_state == TemporalState.ACTIVE)
            if memory_type:
                stmt = stmt.where(Memory.memory_type == memory_type)
            mems = (await db.scalars(stmt)).all()
            return json.dumps([{"id": m.id.hex, "content": m.content, "type": m.memory_type} for m in mems])
    except Exception as e:
        return f"Error: Listing memories failed. Details: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
