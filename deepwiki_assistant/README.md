# DeepWiki Assistant

Ask questions about any GitHub repository using the DeepWiki MCP server tools and generate a clear, grounded explanation with an LLM (Gemini). Output is Markdown.

## Requirements
- A running DeepWiki MCP server exposing tools:
  - `read_wiki_structure`
  - `read_wiki_contents`
  - `ask_question`
- Python deps are already listed in the repo `requirements.txt`:
  - `fastmcp`, `google-generativeai`, `python-dotenv` (and others used elsewhere)
- A Google API key for Gemini

## Quick Start
1. Copy env template and set your key and server URL:
   ```bash
   cp deepwiki_assistant/.env.example deepwiki_assistant/.env
   # Edit .env to set GOOGLE_API_KEY and DEEPWIKI_URL (if different)
   ```

2. Run the client:
   ```bash
   python -m deepwiki_assistant.client \
     --repo owner/repo \
     --question "How do I run the tests and what's the architecture?" \
     --topic getting-started \
     --out deepwiki_answer.md
   ```

Arguments:
- `--server-url` DeepWiki MCP server URL (defaults to `DEEPWIKI_URL` from env or `http://127.0.0.1:8020/mcp`)
- `--repo` GitHub repository in `owner/name` format
- `--question` Your question about the repository
- `--topic` Optional topic slug from the wiki structure to ground the answer further
- `--model` Gemini model (default: `gemini-1.5-flash`)
- `--out` Output markdown file path (default: `deepwiki_answer.md`)

## What it does
- Calls `read_wiki_structure` to get the table of contents
- Optionally calls `read_wiki_contents` for a specific `--topic`
- Calls `ask_question` for an AI-grounded answer
- Uses Gemini to produce a clean, developer-focused Markdown explanation
- Saves the result to `--out`

## Troubleshooting
- Ensure the DeepWiki MCP server is reachable at the URL you configured.
- If Gemini generation fails (e.g., quota), the client falls back to a brief local summary using DeepWiki's answer.
- On Windows code page issues, the console print preview replaces unsupported characters.
