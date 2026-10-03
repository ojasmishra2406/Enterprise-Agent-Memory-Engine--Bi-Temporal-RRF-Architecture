import asyncio
from app.database import SessionLocal
from app.models import Memory, TemporalState
from app.services.llm_service import llm_service
from app.services.retrieval_service import RetrievalService
from app.schemas import SearchRequest
from sqlalchemy import delete
from datetime import datetime, timezone, timedelta
import math

async def run_decay():
    tenant = "decay_tenant"
    agent = "decay_agent"
    
    async with SessionLocal() as db:
        await db.execute(delete(Memory).where(Memory.tenant_id == tenant))
        await db.commit()
        
        text = "The user loves reading sci-fi books."
        emb = await llm_service.generate_embedding(text)
        mem = Memory(
            tenant_id=tenant,
            agent_id=agent,
            content=text,
            memory_type="PREFERENCE", # PREFERENCE type is not EPISODIC or TASK... wait!
            embedding=emb,
            importance=0.8,
            confidence=1.0,
            temporal_state=TemporalState.ACTIVE,
            valid_from=datetime.now(timezone.utc)
        )
        db.add(mem)
        await db.commit()
        
        mem_id = mem.id
        
    async with SessionLocal() as db:
        ret_srv = RetrievalService(db)
        req = SearchRequest(agent_id=agent, query="What does the user like reading?")
        
        print("\n--- BASELINE (T=0) ---")
        res = await ret_srv.hybrid_search(req, tenant)
        base_score = res[0].final_score
        print(f"Base Score: {base_score:.6f}")
        
    decay_rate = 2.67e-7
    
    intervals = [
        ("1 Day", timedelta(days=1)),
        ("1 Week", timedelta(weeks=1)),
        ("1 Month", timedelta(days=30))
    ]
    
    for label, delta in intervals:
        print(f"\n--- {label} ---")
        async with SessionLocal() as db:
            mem = await db.get(Memory, mem_id)
            mem.valid_from = datetime.now(timezone.utc) - delta
            # We also need to change it to EPISODIC since only EPISODIC and TASK decay
            mem.memory_type = "EPISODIC" 
            await db.commit()
            
        async with SessionLocal() as db:
            ret_srv = RetrievalService(db)
            res = await ret_srv.hybrid_search(req, tenant)
            actual_score = res[0].final_score
            
        elapsed_sec = delta.total_seconds()
        expected_score = base_score * math.exp(-decay_rate * elapsed_sec)
        
        print(f"Elapsed seconds: {elapsed_sec}")
        print(f"Actual Score:   {actual_score:.6f}")
        print(f"Expected Score: {expected_score:.6f}")

if __name__ == "__main__":
    asyncio.run(run_decay())
