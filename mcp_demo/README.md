# MCP Demo (Python, stdio)

A minimal Model Context Protocol (MCP) server and client using stdio transport.

## Structure

- `mcp_demo/server.py` — MCP stdio server exposing two tools: `echo(text)` and `add(a, b)`.
- `mcp_demo/client.py` — MCP client that spawns the server, lists tools, and calls both tools.
- `requirements.txt` — Python dependencies.

## Setup

1. Create and activate a virtual environment (recommended):
   - Windows (PowerShell):
     ```powershell
     py -m venv .venv
     .venv\\Scripts\\Activate.ps1
     ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Run

- Start the client (it will spawn the server automatically via stdio):
  ```powershell
  python -m mcp_demo.client
  ```

You should see the available tools and the results of calling `echo` and `add`.

## Notes

- Transport: stdio (the client launches the server subprocess with `python -m mcp_demo.server`).
- If you prefer a different transport (e.g., HTTP/WebSocket), we can extend this example.
