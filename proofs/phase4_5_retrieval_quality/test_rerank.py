import asyncio
from app.database import SessionLocal
from app.models import Memory, TemporalState
from app.services.llm_service import llm_service
from app.services.retrieval_service import RetrievalService
from app.schemas import SearchRequest
from sqlalchemy import delete
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
        
        for text, type_ in texts:
            emb = await llm_service.generate_embedding(text)
            n_mem = Memory(
                tenant_id=tenant_id,
                agent_id=agent_id,
                content=text,
                memory_type=type_,
                embedding=emb,
                importance=0.8,
                confidence=1.0,
                temporal_state=TemporalState.ACTIVE,
                valid_from=datetime.now(timezone.utc)
            )
            db.add(n_mem)
        await db.commit()

async def run_rerank():
    tenant = "rerank_tenant"
    agent = "rerank_agent"
    await setup_data(tenant, agent)
    
    queries = [
        "What food does the user like?",
        "Where did the user go on vacation?",
        "What is the dog's name?"
    ]
    
    async with SessionLocal() as db:
        ret_srv = RetrievalService(db)
        
        for q in queries:
            print(f"\n--- QUERY: {q} ---")
            req = SearchRequest(agent_id=agent, query=q)
            hybrid_results = await ret_srv.hybrid_search(req, tenant)
            for r in hybrid_results:
                print(f"Content: {r.content} | Final Score: {r.final_score:.4f}")
        
        print("\n--- LATENCY BENCHMARK (30 RUNS) ---")
        q = "What food does the user like?"
        req = SearchRequest(agent_id=agent, query=q)
        latencies = []
        for _ in range(30):
            res = await ret_srv.hybrid_search(req, tenant)
            # Find the reranked latency from the structlog output, or we can just measure it manually inside the loop by calling _reranker directly if we want
            pass
        
        # Manually benchmark reranker
        import time
        from app.services.retrieval_service import _reranker
        pairs = [[q, r.content] for r in res]
        for _ in range(30):
            st = time.perf_counter()
            _reranker.predict(pairs)
            latencies.append(time.perf_counter() - st)
            
        import statistics
        print(f"p50 Reranking Latency: {statistics.median(latencies):.4f} seconds")
        print(f"Mean Reranking Latency: {statistics.mean(latencies):.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_rerank())
