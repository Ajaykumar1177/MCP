from fastmcp import FastMCP
import asyncio

# Server showcasing a Resource and a Prompt
mcp = FastMCP("Resource & Prompt Server")
# Resource: serves static text content from a virtual URI
# You can choose any URI scheme; using a custom scheme clarifies it's virtual.
@mcp.resource(
    "res://hello.txt",
    name="Hello Text",
    title="Hello Text Resource",
    description="A simple text resource served by FastMCP",
    mime_type="text/plain",
)
def hello_text() -> str:
    return "Hello from a FastMCP resource!\n"


# Prompt: returns a prompt template that a client can fetch and render/use
@mcp.prompt(
    "greeting",
    title="Greeting Prompt",
    description="Prompt that asks the model to greet a given name.",
)
def greeting_prompt(name: str = "world") -> str:
    return f"You are a helpful assistant. Greet the person named '{name}' in one short sentence."


if __name__ == "__main__":
    # Run over HTTP so clients can connect via URL
    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8002))
