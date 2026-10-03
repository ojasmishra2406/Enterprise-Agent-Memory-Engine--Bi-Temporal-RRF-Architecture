import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.database import SessionLocal
from app.models import Memory
from sqlalchemy import select

async def main():
    tenant = "demo_tenant_fix_2"
    agent = "demo_agent_fix"
    
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("1. Ingesting Fact 1 (User has a dog named Buddy)...")
            res1 = await session.call_tool("ingest_conversation", arguments={
                "tenant_id": tenant,
                "agent_id": agent,
                "session_id": "session_fix_1",
                "messages": [{"role": "user", "content": "I have a dog named Buddy."}]
            })
            print("Response 1:", res1.content[0].text)
            
            print("\n2. Ingesting Fact 2 (Contradiction: User has a cat named Whiskers instead of a dog)...")
            res2 = await session.call_tool("ingest_conversation", arguments={
                "tenant_id": tenant,
                "agent_id": agent,
                "session_id": "session_fix_2",
                "messages": [{"role": "user", "content": "Wait, I don't have a dog. I have a cat named Whiskers."}]
            })
            print("Response 2:", res2.content[0].text)
            
            facts2 = json.loads(res2.content[0].text)
            
            print("\n--- DB QUERY ---")
            async with SessionLocal() as db:
                stmt = select(Memory).where(Memory.tenant_id == tenant).order_by(Memory.valid_from.asc())
                mems = (await db.scalars(stmt)).all()
                for m in mems:
                    print(f"ID: {m.id} | State: {m.temporal_state.name} | SupersededBy: {m.superseded_by_id} | Content: {m.content}")
                    
            print("\n--- LINEAGE TESTS ---")
            for f in facts2:
                mem_id = f["memory_id"]
                print(f"\nLineage for {mem_id} ({f['extracted_fact']['content']}):")
                lin_res = await session.call_tool("get_memory_lineage", arguments={
                    "memory_id": mem_id,
                    "tenant_id": tenant
                })
                print("Response:", lin_res.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
