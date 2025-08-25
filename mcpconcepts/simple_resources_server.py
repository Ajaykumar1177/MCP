from fastmcp import FastMCP
import asyncio
from datetime import datetime

# Simple MCP server exposing one static and one dynamic resource
mcp = FastMCP("Simple Resources Server")

# Static resource: always returns the same text
@mcp.resource(
    "res://hello.txt",
    name="Hello Text",
    title="Hello Text Resource",
    description="A simple static text resource",
    mime_type="text/plain",
)

def hello_text() -> str:
    return "Hello from a static FastMCP resource!\n"

# Dynamic resource: JSON body with current UTC time
@mcp.resource(
    "res://time.json",
    name="Current Time",
    title="Current Time Resource",
    description="Returns the current server time as JSON",
    mime_type="application/json",
)

def current_time() -> str:
    now = datetime.utcnow().isoformat() + "Z"
    return f'{{"utc":"{now}"}}'

if __name__ == "__main__":
    # Use a different port than other examples to avoid conflicts
    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8003))
