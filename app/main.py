from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers import memories

description = """
### The Core Infrastructure for Long-Term Agentic Memory.

This engine provides robust, self-correcting persistence for autonomous agents.

* **Semantic Ingestion:** Automatically extracts facts, constraints, and tasks using localized LLMs.
* **Bi-Temporal Lineage:** Safely preserves historical states of conflicting facts using an append-only architecture.
* **Reciprocal Rank Fusion (RRF):** Queries dense vectors (`pgvector`) and sparse text (`tsvector`) simultaneously natively in PostgreSQL.

*All endpoints are strictly typed, monitored, and engineered for high-throughput concurrency.*
"""

app = FastAPI(
    title="Enterprise Agent Memory Engine",
    description=description,
    version="1.0.0",
    contact={
        "name": "Platform Architecture Team",
    },
)

app.include_router(memories.router)

@app.get("/health", tags=["System Configuration"])
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_state = "ok"
    except Exception as e:
        db_state = str(e)
    return {"status": "ok", "db": db_state}
