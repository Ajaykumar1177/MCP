import asyncio
from fastmcp import Client

async def main():
    math_client = Client("http://127.0.0.1:8000/mcp")  # math_server
    text_client = Client("http://127.0.0.1:8001/mcp")  # text_server

    async with math_client, text_client:
        # Call math tool
        math_result = await math_client.call_tool("multiply", {"a": 6, "b": 7})
        print("Math Result:", math_result.content[0].text)

        # Call text tool
        text_result = await text_client.call_tool("reverse", {"text": "hello"})
        print("Text Result:", text_result.content[0].text)

asyncio.run(main())

# import asyncio
# import sys
# from pathlib import Path
# from mcp.client.session import ClientSession
# from mcp.client.stdio import stdio_client, StdioServerParameters

# async def main():
#     project_root = Path(__file__).resolve().parent  # adjust if needed
#     params = StdioServerParameters(
#         command=sys.executable,
#         args=["-m", "mcp_demo.server"],
#         cwd=str(project_root.parent),
#     )
#     async with stdio_client(params) as (read, write):
#         async with ClientSession(read, write) as session:
#             await session.initialize()
#             print(await session.call_tool("add", {"a": 6, "b": 7}))
#             print(await session.call_tool("echo", {"text": "hello"}))

# asyncio.run(main())