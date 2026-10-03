import asyncio
from app.database import SessionLocal
from app.models import Memory, TemporalState
from app.services.llm_service import llm_service
from app.services.retrieval_service import RetrievalService
from app.schemas import SearchRequest
from sqlalchemy import delete, text
from datetime import datetime, timezone

async def setup_data(tenant_id, agent_id):
    async with SessionLocal() as db:
        await db.execute(delete(Memory).where(Memory.tenant_id == tenant_id))
        await db.commit()
        
        texts = [
            ("User loves tacos.", "PREFERENCE"),
            ("User went to Hawaii for vacation.", "EPISODIC"),
            ("Buddy is a golden retriever.", "EPISODIC"),
            ("User hates coffee.", "PREFERENCE")
        ]
        
        for t, type_ in texts:
            emb = await llm_service.generate_embedding(t)
            n_mem = Memory(
                tenant_id=tenant_id,
                agent_id=agent_id,
                content=t,
                memory_type=type_,
                embedding=emb,
                importance=0.8,
                confidence=1.0,
                temporal_state=TemporalState.ACTIVE,
                valid_from=datetime.now(timezone.utc)
            )
            db.add(n_mem)
        await db.commit()

async def run_ablation():
    tenant = "ablation_tenant"
    agent = "ablation_agent"
    await setup_data(tenant, agent)
    
    query = "What food does the user like?"
    q_emb = await llm_service.generate_embedding(query)
    emb_str = f"[{','.join(map(str, q_emb))}]"
    
    async with SessionLocal() as db:
        ret_srv = RetrievalService(db)
        
        # Dense only
        print("\n--- DENSE ONLY ---")
        dense_sql = text("""
            SELECT id, content, (embedding <=> :embedding_str ::vector) AS distance
            FROM memories
            WHERE temporal_state = 'ACTIVE' AND tenant_id = :tenant_id AND agent_id = :agent_id
            ORDER BY distance ASC LIMIT 5
        """)
        res = await db.execute(dense_sql, {"embedding_str": emb_str, "tenant_id": tenant, "agent_id": agent})
        for r in res.fetchall():
            print(f"Content: {r.content} | Distance: {r.distance:.4f}")
            
        # Sparse only
        print("\n--- SPARSE ONLY ---")
        sparse_sql = text("""
            SELECT id, content, ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS rank
            FROM memories
            WHERE temporal_state = 'ACTIVE' AND tenant_id = :tenant_id AND agent_id = :agent_id
              AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC LIMIT 5
        """)
        res = await db.execute(sparse_sql, {"query": query, "tenant_id": tenant, "agent_id": agent})
        for r in res.fetchall():
            print(f"Content: {r.content} | Rank: {r.rank:.4f}")
            
        # Hybrid
        print("\n--- HYBRID RRF ---")
        req = SearchRequest(agent_id=agent, query=query)
        res = await ret_srv.hybrid_search(req, tenant)
        for r in res:
            print(f"Content: {r.content} | RRF Score: {r.rrf_score:.4f} | Final: {r.final_score:.4f}")

if __name__ == "__main__":
    asyncio.run(run_ablation())
