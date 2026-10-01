import uuid
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.schemas import SearchRequest, SearchResult
from app.models import MemoryType
from app.services.llm_service import llm_service
from app.config import settings

logger = structlog.get_logger(__name__)

class RetrievalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def hybrid_search(self, req: SearchRequest, tenant_id: str) -> list[SearchResult]:
        logger.info("retrieval.hybrid_search.start", query=req.query, tenant_id=tenant_id, agent_id=req.agent_id)
        embedding = await llm_service.generate_embedding(req.query)
        embedding_str = f"[{','.join(map(str, embedding))}]"

        sql_query = text("""
        WITH vector_search AS (
            SELECT 
                id, content, memory_type, importance, confidence, valid_from,
                RANK() OVER (ORDER BY embedding <=> :embedding_str ::vector ASC) AS vector_rank
            FROM memories
            WHERE temporal_state = 'ACTIVE' 
              AND tenant_id = :tenant_id 
              AND agent_id = :agent_id
            ORDER BY embedding <=> :embedding_str ::vector ASC
            LIMIT :pool_size
        ),
        fts_search AS (
            SELECT 
                id, content, memory_type, importance, confidence, valid_from,
                RANK() OVER (ORDER BY ts_rank_cd(to_tsvector('english', content), websearch_to_tsquery('english', :query)) DESC) AS fts_rank
            FROM memories
            WHERE temporal_state = 'ACTIVE' 
              AND tenant_id = :tenant_id 
              AND agent_id = :agent_id
              AND to_tsvector('english', content) @@ websearch_to_tsquery('english', :query)
            ORDER BY ts_rank_cd(to_tsvector('english', content), websearch_to_tsquery('english', :query)) DESC
            LIMIT :pool_size
        ),
        combined AS (
            SELECT
                COALESCE(v.id, f.id) AS memory_id,
                COALESCE(v.content, f.content) AS content,
                COALESCE(v.memory_type, f.memory_type) AS memory_type,
                COALESCE(v.importance, f.importance) AS importance,
                COALESCE(v.confidence, f.confidence) AS confidence,
                COALESCE(v.valid_from, f.valid_from) AS valid_from,
                COALESCE(1.0 / (:rrf_k ::float + v.vector_rank), 0.0) + COALESCE(1.0 / (:rrf_k ::float + f.fts_rank), 0.0) AS rrf_score
            FROM vector_search v
            FULL OUTER JOIN fts_search f ON v.id = f.id
        )
        SELECT 
            memory_id,
            content,
            memory_type,
            importance,
            confidence,
            rrf_score,
            CASE 
                WHEN memory_type IN ('EPISODIC', 'TASK') THEN
                    rrf_score * (1.0 + (importance * 0.2)) * confidence * EXP(-(:decay_rate ::float) * EXTRACT(EPOCH FROM (now() - valid_from)))
                ELSE
                    rrf_score * (1.0 + (importance * 0.2)) * confidence
            END AS final_score
        FROM combined
        ORDER BY final_score DESC
        LIMIT :limit;
        """)

        result = await self.db.execute(sql_query, {
            "embedding_str": embedding_str,
            "tenant_id": tenant_id,
            "agent_id": req.agent_id,
            "query": req.query,
            "limit": req.limit,
            "pool_size": settings.CANDIDATE_POOL_SIZE,
            "rrf_k": settings.RRF_K,
            "decay_rate": settings.DECAY_RATE_PER_SECOND
        })

        rows = result.fetchall()
        results = []
        for row in rows:
            results.append(SearchResult(
                memory_id=row.memory_id,
                content=row.content,
                memory_type=MemoryType(row.memory_type),
                importance=row.importance,
                confidence=row.confidence,
                rrf_score=row.rrf_score,
                final_score=row.final_score
            ))
        
        logger.info("retrieval.hybrid_search.complete", hits=len(results))
        return results
