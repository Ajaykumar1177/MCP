import asyncio
import os
from mcp.server import FastMCP
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

mcp = FastMCP(name="demo-server")


# Load environment variables from the local package .env (works regardless of CWD)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


@mcp.tool()
async def echo(text: str) -> str:
    """Echo back the provided text."""
    return text


@mcp.tool()
async def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@mcp.tool()
async def gemini_complete(prompt: str, model: str = "gemini-1.5-flash") -> str:
    """Call Google Gemini to complete a prompt. Requires GOOGLE_API_KEY in env.

    Args:
        prompt: The user prompt to send to Gemini.
        model:  Gemini model name (e.g., 'gemini-1.5-flash', 'gemini-1.5-pro').
    Returns:
        Text response from the model.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set in environment")

    # Configure the client once per call (simple and safe). You could move to startup if desired.
    genai.configure(api_key=api_key)
    model_client = genai.GenerativeModel(model)

    def _run_sync():
        resp = model_client.generate_content(prompt)
        # The SDK can return candidates; `.text` extracts primary text
        return getattr(resp, "text", "") or ""

    # Run blocking SDK call in a background thread
    return await asyncio.to_thread(_run_sync)


async def main() -> None:
    # Run the MCP server over stdio so clients can spawn it as a subprocess
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
