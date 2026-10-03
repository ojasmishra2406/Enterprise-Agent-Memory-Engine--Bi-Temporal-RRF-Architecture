# Enterprise Agent Memory Engine

**Coverage:** 92% (unmocked) · **Status:** Core Verified · **Protocol:** MCP Compatible

A bi-temporal memory infrastructure for autonomous agents. The engine tracks facts over time, resolves contradictions automatically via an LLM-driven decision layer, and exposes everything through hybrid retrieval and a native Model Context Protocol (MCP) server.

---

## Key Features & Verified Capabilities

### 1. Bi-Temporal Lineage Tracking & Auditability
Data is never destroyed. When an agent learns a fact that contradicts an older one, the previous record transitions from `ACTIVE` to `SUPERSEDED`. A self-referencing foreign key (`superseded_by_id`) bridges the relationship, letting clients traverse the chronological evolution of any fact via the `get_memory_lineage` endpoint.

### 2. Automated Contradiction Resolution (Tri-State Engine)
Incoming facts trigger a similarity sweep against active memories. An extraction model evaluates potential conflicts and routes to one of three states:
*   **`ADD`**: Fact is new and orthogonal.
*   **`UPDATE`**: Fact contradicts a previous state. A flush-ordering bug that could silently orphan memories during intra-batch sequential contradictions was identified and fixed; see *Known Limitations* for the current scope of what's verified.
*   **`NONE`**: Fact is a semantic duplicate. Strengthens confidence and session provenance without duplicating the memory.

### 3. Advanced Retrieval Pipeline (Hybrid RRF + Cross-Encoder)
*   **Hybrid Search**: Native PostgreSQL execution fusing dense vector similarity (`pgvector` cosine distance) with sparse keyword matching (`to_tsvector`) via Reciprocal Rank Fusion (RRF).
*   **Mathematical Time-Decay**: Exponential temporal penalty applied to episodic memory, verified mathematically correct to 6 decimal places at T+1d, T+7d, and T+30d.
*   **Cross-Encoder Reranking**: An `ms-marco-MiniLM-L-6-v2` cross-encoder resolves negation-sensitive ranking failures — verified case: correctly distinguishing "User loves tacos" from "User hates coffee" (+3.24 vs. -6.13 score separation). Measured latency overhead: 24.3ms (p50, 30-run sample).

### 4. Multi-Tenant Access Control
API-key-derived tenant isolation enforced at the query layer — client-supplied `tenant_id` values are rejected outright. Verified against adversarial cross-tenant access tests (seeded data for Tenant B, confirmed inaccessible to Tenant A, and vice versa) with zero observed leakage.

---

## Architecture Overview

### 1. Ingestion & Contradiction Resolution Workflow
![Ingestion & Contradiction Resolution Workflow](docs/images/ingestion_workflow.png)

### 2. Retrieval & Reranking Pipeline
<!-- PLACEHOLDER FOR RETRIEVAL PIPELINE DIAGRAM: Awaiting confirmation on 'Top-K Ranked Memories' label and pipeline order verification -->

---

## Tech Stack

*   **Core Language:** Python 3.12+
*   **API Framework:** FastAPI (v0.110+)
*   **Database:** PostgreSQL 16
*   **Vector Ops:** `pgvector` (HNSW indexing)
*   **ORM & Migrations:** SQLAlchemy 2.0 (async via `asyncpg`) + Alembic
*   **Models:** 
    *   **Local extraction/reasoning:** `llama3.1:8b` (via Ollama)
    *   **Dense embeddings:** `bge-m3` (1024-dimensional)
    *   **Cross-encoder reranker:** `ms-marco-MiniLM-L-6-v2` (`sentence-transformers`)
*   **Agent Protocol:** Native Model Context Protocol (MCP) server using `stdio` JSON-RPC

---

## Quickstart

1. Ensure Docker Desktop and Ollama are installed and running locally.
2. Pull the required local models:
   ```bash
   ollama run llama3.1:8b
   ollama run bge-m3
   ```
3. Boot the environment (stands up Postgres, runs Alembic migrations, starts the API):
   ```bash
   docker-compose up -d --build
   ```
4. Explore the FastAPI OpenAPI playground at `http://localhost:8000/docs`.

### Attaching to an Agent (MCP)

This project bundles an MCP server exposing `ingest_conversation`, `search_memories`, and `get_memory_lineage` to external agents and desktop clients. To attach to an MCP host (e.g., Claude Desktop):

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

---

## Testing & Reliability

*   **Coverage:** 92%, unmocked, running against a live Docker network (real Postgres, real Ollama — no mocked LLM calls).
*   **Bug Resolution:** Found and fixed via testing: an importance-score multiplier that overpowered semantic RRF ranking, and a flush-ordering race condition that could silently orphan memories during intra-batch sequential contradictions.
*   **MCP Integration:** Verified via a real connected client performing multi-tool invocation, including a live failure-injection test (Ollama killed mid-request) confirming graceful error handling and recovery without restarting the server.

---

## Known Limitations

*   **Tuning:** RRF constant (`k=60`) and time-decay rate are standard defaults, not empirically tuned against a labeled dataset.
*   **Negation handling:** Reranking resolves the specific tested case (preference vs. its negation); this is not a general guarantee across all negation phrasing.
*   **Concurrency:** Intra-batch sequential contradiction handling is tested and fixed. True concurrent (simultaneous, multi-request) writes to the same memory have not yet been tested.
*   **Security:** API keys are currently a server-side static mapping (no rotation, hashing, or revocation) — suitable for the current scope, not a production credential store.
*   **Scale:** Not yet tested beyond local, single-node development load.
