import asyncio
import json
import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from fastmcp import Client as MCPClient
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

# Minimal robust import for KernelArguments across SK versions
try:
    from semantic_kernel.contents import KernelArguments  # type: ignore
except Exception:  # pragma: no cover
    try:
        from semantic_kernel.functions.kernel_arguments import KernelArguments  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Semantic Kernel KernelArguments not found. Please upgrade 'semantic-kernel'.") from e

import google.generativeai as genai
SERVER_URL = "http://127.0.0.1:8010/mcp"
load_dotenv()

def _extract_text_from_result(res_obj) -> str:
    try:
        content = getattr(res_obj, "content", None)
        if content:
            first = content[0]
            txt = getattr(first, "text", None)
            if isinstance(txt, str):
                return txt
        txt2 = getattr(res_obj, "text", None)
        if isinstance(txt2, str):
            return txt2
        if isinstance(res_obj, list) and res_obj:
            first = res_obj[0]
            txt3 = getattr(first, "text", None)
            if isinstance(txt3, str):
                return txt3
    except Exception:
        pass
    return str(res_obj)

def _unwrap(value):
    """Return underlying value if this is an SK FunctionResult or similar wrapper."""
    try:
        inner = getattr(value, "value", None)
        if inner is not None:
            return inner
    except Exception:
        pass
    return value

class Summarizer:
    @kernel_function(name="summarize_with_gemini", description="Summarize given prompt with Gemini, returns markdown")
    async def summarize_with_gemini(self, prompt: str, model: str | None = None) -> str:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in environment/.env")
        genai.configure(api_key=api_key)
        system_instruction = (
            "You are a precise research writer. Produce a clean, accurate, and up-to-date report in Markdown. "
            "Use clear headings, bullet lists, short paragraphs, and add a Sources section at the end. "
            "Structure the report as: Overview, What it is, Why it matters, How it works (high-level flow), "
            "Core concepts (Servers, Clients, Tools/Prompts/Resources), Current ecosystem & SDKs, Use cases, "
            "Limitations & open questions, and Sources. Keep it factual and concise."
        )
        preferred = model or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
        try:
            mdl = genai.GenerativeModel(preferred, system_instruction=system_instruction)
            return mdl.generate_content(prompt).text or ""
        except Exception:
            if preferred != "gemini-1.5-flash":
                try:
                    mdl2 = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
                    return mdl2.generate_content(prompt).text or ""
                except Exception:
                    pass
            # local fallback
            return ""

class MCPTools:
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url

    @kernel_function(name="search_web", description="Search the web via MCP server; returns list of results")
    async def search_web(self, query: str, max_results: int = 6) -> List[Dict[str, Any]]:
        client = MCPClient(self.server_url)
        async with client:
            res = await client.call_tool("search_web", {"query": query, "max_results": max_results})
            direct = getattr(res, "result", None)
            if isinstance(direct, list):
                return direct
            txt = _extract_text_from_result(res)
            if txt and txt.strip().startswith("["):
                try:
                    return json.loads(txt)
                except Exception:
                    pass
            if isinstance(res, list):
                return res
            return []

    @kernel_function(name="fetch_url", description="Fetch a URL via MCP server and extract content")
    async def fetch_url(self, url: str, max_chars: int = 8000, insecure: bool = False) -> Dict[str, Any]:
        client = MCPClient(self.server_url)
        async with client:
            res = await client.call_tool("fetch_url", {"url": url, "max_chars": max_chars, "insecure": insecure})
            direct = getattr(res, "result", None)
            if isinstance(direct, dict):
                return direct
            txt = _extract_text_from_result(res)
            if txt and txt.strip().startswith("{"):
                try:
                    return json.loads(txt)
                except Exception:
                    pass
            if isinstance(res, dict):
                return res
            return {}

    @kernel_function(name="get_research_prompt", description="Get the summarization prompt from MCP server")
    async def get_research_prompt(self, topic: str, findings_json: str) -> str:
        client = MCPClient(self.server_url)
        async with client:
            tpl = await client.get_prompt("research_summarize", {"topic": topic, "findings_json": findings_json})
            msg0 = tpl.messages[0]
            content_field = getattr(msg0, "content", None)
            if isinstance(content_field, list) and content_field:
                return getattr(content_field[0], "text", str(content_field[0]))
            return getattr(content_field, "text", str(content_field))

class SKAgent:
    def __init__(self, server_url: str = SERVER_URL, model: str | None = None):
        self.kernel = Kernel()
        self.kernel.add_plugin(MCPTools(server_url), plugin_name="mcp")
        self.kernel.add_plugin(Summarizer(), plugin_name="llm")
        self.model = model or os.getenv("GEMINI_MODEL")

    async def run(self, topic: str, max_results: int = 6, out_file: str = "research_report.md", insecure_ssl: bool = False) -> str:
        # 1) Search
        search_fn = getattr(self.kernel, "get_function")("mcp", "search_web")
        results_obj = await self.kernel.invoke(search_fn, KernelArguments(query=topic, max_results=max_results))  # type: ignore
        results: List[Dict[str, Any]] = _unwrap(results_obj)

        # 2) Fetch top pages
        pages: List[Dict[str, Any]] = []
        for i, r in enumerate(results[: min(5, len(results))]):
            url = r.get("url")
            if not url:
                continue
            fetch_fn = getattr(self.kernel, "get_function")("mcp", "fetch_url")
            try:
                page_obj = await self.kernel.invoke(
                    fetch_fn, KernelArguments(url=url, max_chars=8000, insecure=insecure_ssl)
                )  # type: ignore
            except Exception as e1:
                # try insecure once; if it still fails, skip this URL
                try:
                    page_obj = await self.kernel.invoke(
                        fetch_fn, KernelArguments(url=url, max_chars=8000, insecure=True)
                    )  # type: ignore
                except Exception as e2:
                    print(f"Fetch failed for {url}: {e2}")
                    continue
            page = _unwrap(page_obj)
            page["url"] = url
            page["rank"] = i + 1
            pages.append(page)

        # 3) Build prompt via MCP server prompt
        findings_json = json.dumps({"results": results, "pages": pages})
        get_prompt_fn = getattr(self.kernel, "get_function")("mcp", "get_research_prompt")
        prompt_obj = await self.kernel.invoke(get_prompt_fn, KernelArguments(topic=topic, findings_json=findings_json))  # type: ignore
        prompt: str = _unwrap(prompt_obj)

        # 4) Summarize via Gemini
        summarize_fn = getattr(self.kernel, "get_function")("llm", "summarize_with_gemini")
        report_obj = await self.kernel.invoke(summarize_fn, KernelArguments(prompt=prompt, model=self.model))  # type: ignore
        report_md: str = _unwrap(report_obj)

        # 5) Save
        from pathlib import Path
        Path(out_file).write_text(report_md, encoding="utf-8")
        return report_md

async def run_sk_agent(topic: str, max_results: int = 6, out_file: str = "research_report.md", insecure_ssl: bool = False, model: str | None = None) -> str:
    agent = SKAgent(server_url=SERVER_URL, model=model)
    return await agent.run(topic=topic, max_results=max_results, out_file=out_file, insecure_ssl=insecure_ssl)

if __name__ == "__main__":
    async def _main():
        topic_arg = os.getenv("RA_TOPIC", "").strip()
        if not topic_arg:
            topic_arg = input("Enter research topic: ").strip()
        if not topic_arg:
            raise SystemExit("Topic is required.")
        max_results = int(os.getenv("RA_MAX_RESULTS", "8"))
        out = os.getenv("RA_OUT", "research_report.md")
        insecure_ssl = os.getenv("RA_INSECURE_SSL", "0") == "1"
        model = os.getenv("GEMINI_MODEL", None)
        # Use the Semantic Kernel agent
        md = await run_sk_agent(
            topic=topic_arg,
            max_results=max_results,
            out_file=out,
            insecure_ssl=insecure_ssl,
            model=model,
        )
        # brief preview
        prev = md[:800]
        print(prev, "\n...\n")
    asyncio.run(_main())

