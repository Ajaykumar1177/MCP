import asyncio
import sys
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def main() -> None:
    # Spawn the server via module path so Python can locate it in this project
    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,  # use the same interpreter (venv-safe)
        args=["-m", "mcp_demo.server"],
        cwd=str(project_root),   # ensure package import path is correct
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("Available tools:", [t.name for t in tools_result.tools])

            echo_result = await session.call_tool("echo", {"text": "Hello, MCP!"})
            print("echo() result:", echo_result)

            add_result = await session.call_tool("add", {"a": 2, "b": 3})
            print("add() result:", add_result)

            # Optional: call Gemini (requires GOOGLE_API_KEY set in environment)
            try:
                gem_result = await session.call_tool(
                    "gemini_complete",
                    {"prompt": "Write a short haiku about the ocean.", "model": "gemini-1.5-flash"},
                )
                print("gemini_complete() result:", gem_result)
            except Exception as e:
                print("gemini_complete() call skipped/failed:", e)


if __name__ == "__main__":
    asyncio.run(main())
