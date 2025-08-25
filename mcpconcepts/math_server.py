from fastmcp import FastMCP
import asyncio

mcp = FastMCP("Math Server")

@mcp.tool
def multiply(a: int, b: int) -> int:
    return a * b

if __name__ == "__main__":
    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8000))
