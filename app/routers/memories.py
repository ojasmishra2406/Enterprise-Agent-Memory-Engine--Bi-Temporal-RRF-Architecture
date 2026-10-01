from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas import IngestRequest, IngestResponse, MemoryLineageResponse, MemoryRecordResponse, SearchRequest, SearchResult
from app.services.memory_manager import MemoryManager
from app.services.retrieval_service import RetrievalService
from app.models import Memory, TemporalState
from app.auth import get_current_tenant
import uuid

router = APIRouter(prefix="/v1/memories", tags=["memories"])

@router.post("/ingest", response_model=IngestResponse)
async def ingest_memory(req: IngestRequest, tenant_id: str = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    mgr = MemoryManager(db)
    res_list = await mgr.ingest_transcript(req, tenant_id)
    return IngestResponse(session_id=req.session_id, processed_count=len(res_list), results=res_list)

@router.get("/{memory_id}/lineage", response_model=MemoryLineageResponse)
async def get_lineage(memory_id: uuid.UUID, tenant_id: str = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    mgr = MemoryManager(db)
    res = await mgr.get_memory_lineage(memory_id, tenant_id)
    if not res:
        raise HTTPException(status_code=404, detail="Memory not found")
    return res

@router.get("", response_model=list[MemoryRecordResponse])
async def list_mem(agent_id: str, include_superseded: bool = False, tenant_id: str = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    stmt = select(Memory).where(Memory.tenant_id == tenant_id).where(Memory.agent_id == agent_id)
    if not include_superseded:
        stmt = stmt.where(Memory.temporal_state == TemporalState.ACTIVE)
    return (await db.scalars(stmt)).all()

@router.post("/search", response_model=list[SearchResult])
async def search_memories(req: SearchRequest, tenant_id: str = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    service = RetrievalService(db)
    return await service.hybrid_search(req, tenant_id)
