import asyncio
import os
import sys
import json
from typing import Any, Dict, List
from dotenv import load_dotenv
import re

import google.generativeai as genai
from fastmcp import Client as MCPClient
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

SERVER_URL = "http://127.0.0.1:8010/mcp"
load_dotenv()


# LLM Wrapper 
class LLM:
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set in .env")
        genai.configure(api_key=api_key)
        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"

    async def ask(self, query: str) -> str:
        """Let the LLM decide what to do with the query."""
        system_instruction = (
            "You are an assistant with access to tools:\n"
            "1. search_web(query) → Use when user asks to explain a concept or learn a topic.\n"
            "2. fetch_url(url) → Use when user asks for websites/resources/links. "
            "In that case, return actual URLs (not queries) inside fetch_url.\n"
            "Decide which tool is needed and respond with a JSON action like:\n"
            '{"action": "search_web", "args": {"query": "artificial intelligence"}}\n'
            "or {\"action\": \"fetch_url\", \"args\": {\"url\": \"https://example.com\"}}.\n"
            "If no tool is needed, just answer normally."
        )

        mdl = genai.GenerativeModel(self.model, system_instruction=system_instruction)
        res = mdl.generate_content(query).text
        return res or ""


class MCPTools:
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url

    # Helper: unwrap different return shapes from FastMCP CallToolResult
    def _unwrap_result(self, res: Any) -> Any:
        direct = getattr(res, "result", None)
        if direct is not None:
            return direct
        content = getattr(res, "content", None)
        if isinstance(content, list) and content:
            first = content[0]
            txt = getattr(first, "text", None)
            if txt is not None:
                return txt
        data = getattr(res, "data", None)
        if data is not None:
            return data
        return res

    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        async with MCPClient(self.server_url) as client:
            res = await client.call_tool("search_web", {"query": query, "max_results": max_results})
            raw = self._unwrap_result(res)
            if isinstance(raw, str):
                try:
                    arr = json.loads(raw)
                except Exception:
                    arr = []
            elif isinstance(raw, list):
                arr = raw
            else:
                arr = []
            return arr

    async def fetch_url(self, url: str, max_chars: int = 4000) -> Dict[str, Any]:
        async with MCPClient(self.server_url) as client:
            res = await client.call_tool("fetch_url", {"url": url, "max_chars": max_chars})
            raw = self._unwrap_result(res)
            if isinstance(raw, str):
                try:
                    obj = json.loads(raw)
                except Exception:
                    obj = {}
            elif isinstance(raw, dict):
                obj = raw
            else:
                obj = {}
            return obj


class SimpleAgent:
    def __init__(self, server_url: str = SERVER_URL, model: str | None = None):
        self.llm = LLM(model)
        self.tools = MCPTools(server_url)

    async def run(self, user_query: str) -> str:
        # Step 1: LLM decides what to do
        decision = await self.llm.ask(user_query)

        # --- Clean JSON output from Gemini (strip ```json ... ```) ---
        cleaned = re.sub(r"```(?:json)?", "", decision, flags=re.IGNORECASE).strip("` \n")

        try:
            action = json.loads(cleaned)
        except Exception:
            # Fallback: ask to produce a concise paragraph directly
            fallback = await self.llm.ask(
                "Write a concise paragraph explaining the topic in simple terms: " + user_query
            )
            return fallback

        # Step 2: Handle actions
        if action.get("action") == "search_web":
            results = await self.tools.search_web(**action["args"])

            # Extract snippets + titles for context
            snippets = []
            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                if title or snippet:
                    snippets.append(f"{title}: {snippet}")

            if not snippets:
                # Graceful fallback: answer directly as a paragraph
                direct = await self.llm.ask(
                    "Write a concise paragraph explaining the topic in simple terms: "
                    + user_query
                )
                return direct

            # Ask LLM to turn snippets into a paragraph
            summary = await self.llm.ask(
                "Write a concise paragraph explaining the topic based on these search results:\n\n"
                + "\n".join(snippets[:8])
            )
            return summary


        elif action.get("action") == "fetch_url":
            urls = action["args"]
            if isinstance(urls, dict):  # single url
                urls = [urls]

            summaries = []
            for u in urls:
                page = await self.tools.fetch_url(**u)
                content = (page.get("text") or "")[:1500]
                summary = await self.llm.ask(
                    f"Summarize this webpage into a clear paragraph:\n\n{content}"
                )
                link = u.get("url")
                summaries.append(f"🔗 {link}\n{summary}")

            return "\n\n".join(summaries)

        else:
            return f"🤖 {decision}"

# ------------------ Main ------------------
async def main():
    agent = SimpleAgent()
    query = input("Ask me something: ")
    reply = await agent.run(query)
    print(reply)


if __name__ == "__main__":
    asyncio.run(main())

