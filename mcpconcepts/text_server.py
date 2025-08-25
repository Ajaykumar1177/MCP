from fastmcp import FastMCP
import asyncio

mcp = FastMCP("Text Server")

@mcp.tool
def reverse(text: str) -> str:
    return text[::-1]

if __name__ == "__main__":
    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8001))

