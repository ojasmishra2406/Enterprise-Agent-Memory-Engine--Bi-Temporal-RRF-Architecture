import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Invoking get_memory_lineage on 87eba12e-9305-4641-ac76-e81c1125284c...")
            res = await session.call_tool("get_memory_lineage", arguments={
                "memory_id": "87eba12e-9305-4641-ac76-e81c1125284c",
                "tenant_id": "demo_tenant"
            })
            print("Response:", res.content)

asyncio.run(main())
