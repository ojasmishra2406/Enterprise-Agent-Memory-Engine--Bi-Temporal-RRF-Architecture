import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys
import uuid

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )
    
    print("Connecting to MCP server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            print(f"Handshake successful! Server capabilities: {init_res.capabilities}")
            
            # --- TASK 4.1: Single Ingest ---
            print("\n--- Invoking ingest_conversation ---")
            try:
                res = await session.call_tool("ingest_conversation", arguments={
                    "tenant_id": "demo_tenant",
                    "agent_id": "demo_agent",
                    "session_id": "session_1",
                    "messages": [{"role": "user", "content": "My name is Alice and I love hiking."}]
                })
                print("Response:", res.content)
            except Exception as e:
                print("Error:", e)
                
            # --- TASK 4.1: Search ---
            print("\n--- Invoking search_memories ---")
            try:
                res = await session.call_tool("search_memories", arguments={
                    "tenant_id": "demo_tenant",
                    "agent_id": "demo_agent",
                    "query": "What does the user like?"
                })
                print("Response:", res.content)
            except Exception as e:
                print("Error:", e)

            # --- TASK 4.3: Multi-Call Realistic Sequence ---
            print("\n--- TASK 4.3: Realism Sequence ---")
            print("1. Ingesting Fact 1 (User has a dog named Buddy)...")
            res_fact1 = await session.call_tool("ingest_conversation", arguments={
                "tenant_id": "demo_tenant",
                "agent_id": "demo_agent",
                "session_id": "session_2",
                "messages": [{"role": "user", "content": "I have a golden retriever named Buddy."}]
            })
            print("Response:", res_fact1.content)

            print("2. Ingesting Fact 2 (Contradiction: User has a cat named Whiskers instead of a dog)...")
            res_fact2 = await session.call_tool("ingest_conversation", arguments={
                "tenant_id": "demo_tenant",
                "agent_id": "demo_agent",
                "session_id": "session_3",
                "messages": [{"role": "user", "content": "Wait, I don't have a dog. I have a cat named Whiskers."}]
            })
            print("Response:", res_fact2.content)
            
            # Extract the UUID of the superseded memory
            new_memories = json.loads(res_fact2.content[0].text)
            
            # We want to find the ID of the new active memory
            active_id = None
            if new_memories:
                active_id = new_memories[0]["id"]
            
            print(f"3. Searching for user's pet...")
            res_search = await session.call_tool("search_memories", arguments={
                "tenant_id": "demo_tenant",
                "agent_id": "demo_agent",
                "query": "What pet does the user have?"
            })
            print("Response:", res_search.content)
            
            if active_id:
                print(f"4. Retrieving lineage for the memory {active_id}...")
                res_lineage = await session.call_tool("get_memory_lineage", arguments={
                    "memory_id": active_id,
                    "tenant_id": "demo_tenant"
                })
                print("Response:", res_lineage.content)

if __name__ == "__main__":
    asyncio.run(main())
