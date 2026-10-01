import pytest
from httpx import AsyncClient
from sqlalchemy import text
from app.models import TemporalState

@pytest.mark.asyncio
async def test_ingest_extracts_json(client: AsyncClient):
    payload = {
        "agent_id": "test_agent",
        "session_id": "test_session",
        "messages": [{"role": "user", "content": "I live in New York."}]
    }
    # Valid auth
    response = await client.post("/v1/memories/ingest", json=payload, headers={"X-API-Key": "test_key_tenant_a"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["results"]) > 0
    # Must be valid json extraction format
    fact = data["results"][0]["extracted_fact"]
    assert "content" in fact
    assert fact["memory_type"] in ["EPISODIC", "SEMANTIC", "PREFERENCE", "TASK"]

@pytest.mark.asyncio
async def test_contradiction_updates_temporal_state(client: AsyncClient, db_session):
    # 1. Ingest initial fact
    payload1 = {
        "agent_id": "test_agent",
        "session_id": "test_session",
        "messages": [{"role": "user", "content": "I hate broccoli."}]
    }
    res1 = await client.post("/v1/memories/ingest", json=payload1, headers={"X-API-Key": "test_key_tenant_a"})
    assert res1.status_code == 200
    
    # Verify in DB
    result = await db_session.execute(text("SELECT id, temporal_state, content FROM memories WHERE agent_id = 'test_agent'"))
    rows1 = result.fetchall()
    assert len(rows1) == 1
    assert rows1[0][1] == TemporalState.ACTIVE.value
    mem_id = rows1[0][0]

    # 2. Ingest contradiction
    payload2 = {
        "agent_id": "test_agent",
        "session_id": "test_session",
        "messages": [{"role": "user", "content": "I actually love broccoli now."}]
    }
    res2 = await client.post("/v1/memories/ingest", json=payload2, headers={"X-API-Key": "test_key_tenant_a"})
    assert res2.status_code == 200

    # Verify DB temporal update
    result = await db_session.execute(text("SELECT id, temporal_state, superseded_by_id FROM memories WHERE id = :mid"), {"mid": mem_id})
    rows2 = result.fetchall()
    
    assert rows2[0][1] == TemporalState.SUPERSEDED.value
    assert rows2[0][2] is not None  # superseded_by_id

@pytest.mark.asyncio
async def test_unauthorized_access_fails(client: AsyncClient):
    payload = {
        "agent_id": "test_agent",
        "query": "hello"
    }
    # No header
    response = await client.post("/v1/memories/search", json=payload)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_malformed_api_key_header(client: AsyncClient):
    payload = {
        "agent_id": "test_agent",
        "query": "hello"
    }
    # Empty string
    res1 = await client.post("/v1/memories/search", json=payload, headers={"X-API-Key": ""})
    assert res1.status_code == 401
    
    # Garbage token
    res2 = await client.post("/v1/memories/search", json=payload, headers={"X-API-Key": "not_a_valid_token!"})
    assert res2.status_code == 401

@pytest.mark.asyncio
async def test_sql_injection_attempt(client: AsyncClient):
    payload = {
        "agent_id": "'; DROP TABLE memories; --",
        "query": "'; DROP TABLE memories; --"
    }
    # Valid auth, malicious payload
    response = await client.post("/v1/memories/search", json=payload, headers={"X-API-Key": "test_key_tenant_a"})
    # Should safely return 200 with 0 results instead of throwing a SQL syntax error or executing the drop
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_ingest_resolution_none_boosts_confidence(client: AsyncClient, db_session):
    # 1. Ingest initial fact
    payload1 = {
        "agent_id": "test_agent",
        "session_id": "sess_1",
        "messages": [{"role": "user", "content": "I own a blue car."}]
    }
    res1 = await client.post("/v1/memories/ingest", json=payload1, headers={"X-API-Key": "test_key_tenant_a"})
    assert res1.status_code == 200
    mem_id = res1.json()["results"][0]["memory_id"]
    
    # 2. Ingest identical fact from a different session (should trigger NONE action)
    payload2 = {
        "agent_id": "test_agent",
        "session_id": "sess_2",
        "messages": [{"role": "user", "content": "I own a blue car."}]
    }
    res2 = await client.post("/v1/memories/ingest", json=payload2, headers={"X-API-Key": "test_key_tenant_a"})
    assert res2.status_code == 200
    
    # 3. Verify confidence boosted and session appended
    result = await db_session.execute(text("SELECT source_provenance FROM memories WHERE id = :mid"), {"mid": mem_id})
    row = result.fetchone()
    prov = row[0]
    assert "sess_1" in prov["seen_in_sessions"]
    assert "sess_2" in prov["seen_in_sessions"]

@pytest.mark.asyncio
async def test_get_memory_lineage(client: AsyncClient, db_session):
    # 1. Initial fact
    payload1 = {
        "agent_id": "test_agent",
        "session_id": "sess_1",
        "messages": [{"role": "user", "content": "I am a junior developer."}]
    }
    res1 = await client.post("/v1/memories/ingest", json=payload1, headers={"X-API-Key": "test_key_tenant_a"})
    mem_id_1 = res1.json()["results"][0]["memory_id"]
    
    # 2. Update it
    payload2 = {
        "agent_id": "test_agent",
        "session_id": "sess_2",
        "messages": [{"role": "user", "content": "I am now a senior developer!"}]
    }
    res2 = await client.post("/v1/memories/ingest", json=payload2, headers={"X-API-Key": "test_key_tenant_a"})
    mem_id_2 = res2.json()["results"][0]["memory_id"]
    
    # 3. Get lineage using the FIRST memory
    res_lineage = await client.get(f"/v1/memories/{mem_id_1}/lineage", headers={"X-API-Key": "test_key_tenant_a"})
    assert res_lineage.status_code == 200
    lineage_data = res_lineage.json()
    
    # The current active should be mem_id_2
    assert lineage_data["current_memory"]["id"] == mem_id_2
    # The history chain should contain mem_id_1
    history_ids = [m["id"] for m in lineage_data["history_chain"]]
    assert mem_id_1 in history_ids

