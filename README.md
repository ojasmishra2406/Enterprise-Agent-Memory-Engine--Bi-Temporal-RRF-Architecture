# Enterprise Agent Memory Engine

A high-performance, standalone memory infrastructure designed for autonomous AI agents. The engine provides bi-temporal tracking, semantic vector search, and automated contradiction resolution to give AI agents long-term, self-correcting persistence.

## Architecture & Tech Stack
* **Language:** Python 3.12+ (Strictly Typed)
* **API:** FastAPI (v0.110+)
* **Database:** PostgreSQL 16 with `pgvector` (HNSW indices) and GIN indexing for Full-Text Search.
* **ORM:** SQLAlchemy 2.0 (Async via `asyncpg`) + Alembic migrations.
* **Embeddings & Extraction:** Integrates with local inference via Ollama (`llama3.1:8b` for fact extraction and logic, `bge-m3` for 1024-dimensional embeddings).
* **Protocol:** Built-in Model Context Protocol (MCP) Server for immediate integration into external multi-agent networks and desktop environments.

## Core Capabilities

1. **Automated Contradiction Resolution (The Tri-State Engine):** 
   Incoming facts automatically trigger a localized similarity sweep against active memories. An extraction LLM evaluates conflicts and enforces a strict deterministic tri-state resolution:
   - **`ADD`**: The fact is entirely new and orthogonal.
   - **`UPDATE`**: The fact contradicts or updates a previous state. The engine executes atomic state transitions.
   - **`NONE`**: The fact is a semantic duplicate. The engine strengthens confidence and provenance metadata without duplicating embeddings.

2. **Bi-Temporal Lineage Tracking:**
   Data is never destroyed. When a fact is `UPDATE`d, the previous record's state transitions from `ACTIVE` to `SUPERSEDED`, and a self-referencing foreign key (`superseded_by_id`) bridges the relationship. This enables bidirectional, chronological traversal of an agent's memory evolution.

3. **Hybrid Retrieval with Reciprocal Rank Fusion (RRF):**
   A specialized algorithm natively executes inside PostgreSQL to fuse dense vector similarity (`pgvector` cosine distance) with sparse keyword matching (`to_tsvector`). A mathematical temporal decay penalty is selectively applied to episodic memory retrieval.

## Quickstart

1. Ensure Docker Desktop and Ollama are installed and running locally.
2. Pull the necessary local models:
   ```bash
   ollama run llama3.1:8b
   ollama run bge-m3
   ```
3. Boot the environment:
   ```bash
   docker-compose up -d --build
   ```
4. Explore the FastAPI OpenAPI docs at `http://localhost:8000/docs`.

### Attaching via MCP
To attach the engine directly to an MCP host like Claude Desktop, add the following to your configuration:
```json
{
  "mcpServers": {
    "agent-memory-engine": {
      "command": "docker-compose",
      "args": ["run", "--rm", "-i", "mcp_server"],
      "env": {}
    }
  }
}
```
