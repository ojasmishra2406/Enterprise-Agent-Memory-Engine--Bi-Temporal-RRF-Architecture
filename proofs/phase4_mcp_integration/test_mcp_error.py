import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )
    
    print("Connecting to MCP server for Error Test...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("Sending ingest request... KILL OLLAMA NOW!")
            try:
                res = await session.call_tool("ingest_conversation", arguments={
                    "tenant_id": "demo_tenant",
                    "agent_id": "demo_agent",
                    "session_id": "session_error",
                    "messages": [{"role": "user", "content": "I like breaking things."}]
                })
                print("Response:", res.content)
            except Exception as e:
                print("Unexpected Error Class:", e)

if __name__ == "__main__":
    asyncio.run(main())
