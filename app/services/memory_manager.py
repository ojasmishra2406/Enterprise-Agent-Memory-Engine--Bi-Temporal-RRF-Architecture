from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Memory, TemporalState, current_utc_time
from app.schemas import IngestRequest, FactResolutionReport, ResolutionAction
from app.services.llm_service import llm_service
from app.config import settings
import uuid

class MemoryManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_transcript(self, req: IngestRequest, tenant_id: str) -> list[FactResolutionReport]:
        facts = await llm_service.extract_salient_facts(req.messages)
        reports = []
        for fact in facts:
            embedding = await llm_service.generate_embedding(fact.content)
            
            sim_score = 1 - Memory.embedding.cosine_distance(embedding)
            search_stmt = (
                select(Memory)
                .where(Memory.tenant_id == tenant_id)
                .where(Memory.agent_id == req.agent_id)
                .where(Memory.temporal_state == TemporalState.ACTIVE)
                .where(sim_score >= settings.SIMILARITY_THRESHOLD)
                .order_by(Memory.embedding.cosine_distance(embedding).asc())
                .limit(settings.CONTRADICTION_TOP_K)
            )
            candidate_list = (await self.db.scalars(search_stmt)).all()
            valid_candidate_ids = {c.id for c in candidate_list}
            
            if not candidate_list:
                act = ResolutionAction.ADD
                t_ids = []
                reason_msg = "No candidates found."
                upd_content = None
            else:
                # Deterministic check for exact duplicates to bypass LLM
                exact_match = next((c for c in candidate_list if c.content.strip().lower() == fact.content.strip().lower()), None)
                
                if exact_match:
                    act = ResolutionAction.NONE
                    t_ids = [exact_match.id]
                    reason_msg = "Deterministic exact match bypass."
                    upd_content = None
                else:
                    llm_dec = await llm_service.evaluate_contradiction(fact, candidate_list)
                    act = llm_dec.action
                    t_ids = [tid for tid in llm_dec.target_memory_ids if tid in valid_candidate_ids]
                    reason_msg = llm_dec.reason
                    upd_content = llm_dec.updated_content
                    
                    if act == ResolutionAction.UPDATE and not t_ids:
                        act = ResolutionAction.ADD

            new_id = None
            super_ids = []

            if act == ResolutionAction.ADD:
                n_mem = Memory(
                    tenant_id=tenant_id,
                    agent_id=req.agent_id,
                    content=fact.content,
                    memory_type=fact.memory_type,
                    embedding=embedding,
                    importance=fact.importance,
                    confidence=fact.confidence,
                    source_provenance={"seen_in_sessions": [req.session_id], **req.metadata},
                    temporal_state=TemporalState.ACTIVE,
                    valid_from=current_utc_time()
                )
                self.db.add(n_mem)
                await self.db.flush()
                new_id = n_mem.id
                
            elif act == ResolutionAction.UPDATE:
                fin_content = upd_content or fact.content
                fin_emb = embedding if not upd_content else await llm_service.generate_embedding(fin_content)
                
                upd_stmt = select(Memory).where(Memory.id.in_(t_ids)).where(Memory.tenant_id == tenant_id).where(Memory.temporal_state == TemporalState.ACTIVE).with_for_update()
                t_mems = (await self.db.scalars(upd_stmt)).all()
                
                n_mem = Memory(
                    tenant_id=tenant_id,
                    agent_id=req.agent_id,
                    content=fin_content,
                    memory_type=fact.memory_type,
                    embedding=fin_emb,
                    importance=fact.importance,
                    confidence=fact.confidence,
                    source_provenance={
                        "seen_in_sessions": [req.session_id],
                        "supersedes_ids": [str(m.id) for m in t_mems],
                        "contradiction_reason": reason_msg,
                        **req.metadata
                    },
                    temporal_state=TemporalState.ACTIVE,
                    valid_from=current_utc_time()
                )
                self.db.add(n_mem)
                await self.db.flush()
                new_id = n_mem.id
                
                for om in t_mems:
                    om.temporal_state = TemporalState.SUPERSEDED
                    om.valid_to = current_utc_time()
                    om.superseded_by_id = n_mem.id
                    super_ids.append(om.id)
                    
                await self.db.flush()
                    
            elif act == ResolutionAction.NONE:
                if t_ids:
                    match_stmt = select(Memory).where(Memory.id == t_ids[0]).where(Memory.tenant_id == tenant_id).with_for_update()
                    m_mem = await self.db.scalar(match_stmt)
                    if m_mem:
                        m_mem.confidence = max(m_mem.confidence, fact.confidence)
                        s_arr = m_mem.source_provenance.get("seen_in_sessions", [])
                        if req.session_id not in s_arr:
                            s_arr.append(req.session_id)
                        m_mem.source_provenance = {**m_mem.source_provenance, "seen_in_sessions": s_arr}
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(m_mem, "source_provenance")
                        await self.db.flush()
                        new_id = m_mem.id
            
            reports.append(FactResolutionReport(
                extracted_fact=fact,
                action_taken=act,
                memory_id=new_id,
                superseded_memory_ids=super_ids,
                reason=reason_msg
            ))
            
        return reports

    async def get_memory_lineage(self, memory_id: uuid.UUID, tenant_id: str):
        stmt = select(Memory).where(Memory.id == memory_id, Memory.tenant_id == tenant_id)
        start_mem = await self.db.scalar(stmt)
        if not start_mem:
            return None

        # 1. Walk forward to find the root active (or latest) memory
        curr = start_mem
        while curr.superseded_by_id:
            print('DEBUG: Executing lineage loop!')
            fwd_stmt = select(Memory).where(Memory.id == curr.superseded_by_id, Memory.tenant_id == tenant_id)
            nxt = await self.db.scalar(fwd_stmt)
            if not nxt:
                break
            curr = nxt
            
        root_mem = curr
        
        # 2. Breadth-first traversal backward
        history = []
        current_level_ids = [root_mem.id]
        
        while current_level_ids:
            bwd_stmt = select(Memory).where(Memory.superseded_by_id.in_(current_level_ids), Memory.tenant_id == tenant_id).order_by(Memory.valid_from.desc())
            ancestors = (await self.db.scalars(bwd_stmt)).all()
            if not ancestors:
                break
            history.extend(ancestors)
            current_level_ids = [a.id for a in ancestors]
            
        return {"current_memory": root_mem, "history_chain": history}
