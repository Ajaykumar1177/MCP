import asyncio
import json
from typing import List, Dict, Any

from fastmcp import Client
import os
from dotenv import load_dotenv
import google.generativeai as genai
import argparse
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
try:
    # Newer SK versions
    from semantic_kernel.contents import KernelArguments
except Exception:  # pragma: no cover
    KernelArguments = None  # type: ignore

SERVER_URL = "http://127.0.0.1:8010/mcp"

load_dotenv()


def _extract_text_from_result(res_obj) -> str:
    """Normalize possible fastmcp tool result shapes to text."""
    # Common shapes:
    # - object with .content: list where first has .text
    # - object with .text
    # - list of content items
    # - fallback to str
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


def _safe_print_preview(text: str, limit: int = 800) -> None:
    preview = text[:limit]
    try:
        print(preview, "\n...\n")
    except UnicodeEncodeError:
        # Fallback: replace un-encodable characters
        print(preview.encode("cp1252", errors="replace").decode("cp1252"), "\n...\n")

async def research(topic: str, max_results: int = 5, insecure_ssl: bool = False) -> Dict[str, Any]:
    client = Client(SERVER_URL)
    async with client:
        # 1) search
        search_res = await client.call_tool("search_web", {"query": topic, "max_results": max_results})
        # Try to parse either JSON string content or direct Python object
        results: List[Dict[str, Any]]
        parsed = None
        # direct result attribute used by some clients
        direct = getattr(search_res, "result", None)
        if isinstance(direct, (list, dict)):
            parsed = direct
        if parsed is None:
            search_txt = _extract_text_from_result(search_res)
            if search_txt and search_txt.strip().startswith(("[", "{")):
                try:
                    parsed = json.loads(search_txt)
                except Exception:
                    parsed = None
        if parsed is None and isinstance(search_res, (list, dict)):
            parsed = search_res
        if not isinstance(parsed, list):
            raise RuntimeError("search_web returned unexpected shape; expected list of results")
        results = parsed  # type: ignore[assignment]

        # 2) fetch a few top links
        pages: List[Dict[str, Any]] = []
        for i, r in enumerate(results[: min(5, len(results))]):
            url = r.get("url")
            if not url:
                continue
            # First attempt respects global insecure flag; on cert failure retry once with insecure=True
            try:
                page = await client.call_tool("fetch_url", {"url": url, "max_chars": 8000, "insecure": insecure_ssl})
            except Exception as e:
                msg = str(e)
                if "CERTIFICATE_VERIFY_FAILED" in msg or "self-signed certificate" in msg:
                    try:
                        page = await client.call_tool("fetch_url", {"url": url, "max_chars": 8000, "insecure": True})
                    except Exception:
                        continue
                else:
                    continue
            page_parsed = None
            direct_p = getattr(page, "result", None)
            if isinstance(direct_p, dict):
                page_parsed = direct_p
            if page_parsed is None:
                page_txt = _extract_text_from_result(page)
                if page_txt and page_txt.strip().startswith(("[", "{")):
                    try:
                        page_parsed = json.loads(page_txt)
                    except Exception:
                        page_parsed = None
            if page_parsed is None and isinstance(page, dict):
                page_parsed = page
            if not isinstance(page_parsed, dict):
                continue
            page_obj = page_parsed
            pages.append({"rank": i + 1, "url": url, **page_obj})

        # 3) get prompt template
        prompt_tpl = await client.get_prompt("research_summarize", {"topic": topic, "findings_json": json.dumps({"results": results, "pages": pages})})
        # Extract prompt text robustly across content shapes
        msg0 = prompt_tpl.messages[0]
        content_field = getattr(msg0, "content", None)
        if isinstance(content_field, list) and content_field:
            prompt_text = getattr(content_field[0], "text", str(content_field[0]))
        else:
            prompt_text = getattr(content_field, "text", str(content_field))

        return {
            "prompt": prompt_text,
            "results": results,
            "pages": pages,
        }


class SaveSkills:
    @kernel_function(name="save_markdown", description="Save markdown content to a file and return the file path.")
    async def save_markdown(self, content: str, filename: str = "research_report.md") -> str:
        from pathlib import Path
        out_path = Path(filename).resolve()
        out_path.write_text(content, encoding="utf-8")
        return str(out_path)


async def research_and_summarize(topic: str, max_results: int = 5, out_file: str | None = None, insecure_ssl: bool = False) -> str:
    data = await research(topic, max_results=max_results, insecure_ssl=insecure_ssl)
    results = data["results"]
    pages = data["pages"]
    prompt = data["prompt"]

    # Use Gemini to produce a clean markdown report (inline config)
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
    # Prefer model from CLI/env; default to flash for better quota
    preferred_model = (
        os.getenv("GEMINI_MODEL")
        or getattr(globals().get("_ARGS", None), "model", None)
        or "gemini-1.5-flash"
    )
    model = genai.GenerativeModel(preferred_model, system_instruction=system_instruction)
    try:
        report_md = model.generate_content(prompt).text or ""
    except Exception:
        # Second try: switch to flash if not already
        try:
            if preferred_model != "gemini-1.5-flash":
                model2 = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
                report_md = model2.generate_content(prompt).text or ""
            else:
                raise RuntimeError("Already using fallback model")
        except Exception:
            # Fallback: build a structured markdown summary locally so the run still succeeds
            overview = (
                f"This brief summarizes public information related to '{topic}'. It aggregates top search "
                "results and quick page extracts as a snapshot."
            )
            lines = [
                f"# Research Brief: {topic}",
                "",
                "## Overview",
                overview,
                "",
                "## Key Findings (titles)",
            ]
            for r in results[: max_results]:
                title = r.get("title") or r.get("snippet") or r.get("url", "")
                url = r.get("url", "")
                if title:
                    lines.append(f"- {title} ({url})")
            lines.append("")
            lines.append("## Extracted Page Previews")
            for p in pages:
                title = p.get("title") or "(no title)"
                url = p.get("url", "")
                preview = (p.get("text") or "").strip()[:500]
                lines.append(f"- {title} — {url}\n  \n  {preview}…")
            lines.append("")
            lines.append("## Sources")
            for r in results[: max_results]:
                src = r.get("url", "")
                if src:
                    lines.append(f"- {src}")
            lines.append("")
            lines.append(
                "_Note: Gemini summarization was unavailable (e.g., quota). This is a locally constructed summary from search results and page previews._"
            )
            report_md = "\n".join(lines)

    # Save via Semantic Kernel if available; fallback to direct write
    if out_file:
        saved = False
        try:
            kernel = Kernel()
            kernel.add_plugin(SaveSkills(), plugin_name="io")
            # Preferred: pass KernelArguments if available
            if KernelArguments is not None:
                try:
                    await kernel.invoke("io", "save_markdown", KernelArguments(content=report_md, filename=out_file))
                    saved = True
                except Exception:
                    # Try function object style
                    try:
                        func = getattr(kernel, "get_function")("io", "save_markdown")
                        await kernel.invoke(func, KernelArguments(content=report_md, filename=out_file))
                        saved = True
                    except Exception:
                        saved = False
            if not saved:
                # Older SK versions: use dict arguments
                try:
                    await kernel.invoke("io", "save_markdown", arguments={"content": report_md, "filename": out_file})
                    saved = True
                except Exception:
                    try:
                        func = getattr(kernel, "get_function")("io", "save_markdown")
                        await kernel.invoke(func, arguments={"content": report_md, "filename": out_file})
                        saved = True
                    except Exception:
                        saved = False
        except Exception:
            saved = False
        if not saved:
            from pathlib import Path
            Path(out_file).write_text(report_md, encoding="utf-8")

    return report_md


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Research Assistant Client")
    parser.add_argument("--topic", type=str, help="Research topic (if omitted, you will be prompted)")
    parser.add_argument("--max-results", type=int, default=6, help="Max search results")
    parser.add_argument("--out", type=str, default="research_report.md", help="Output markdown file path")
    parser.add_argument("--insecure-ssl", action="store_true", help="Disable SSL verification for fetch_url (not recommended)")
    parser.add_argument("--model", type=str, default=None, help="Gemini model name (e.g., gemini-1.5-flash or gemini-1.5-pro)")
    args = parser.parse_args()
    # Make args accessible for model selection
    _ARGS = args

    topic_arg = args.topic or input("Enter research topic: ").strip()
    if not topic_arg:
        raise SystemExit("Topic is required.")

    async def _main():
        md = await research_and_summarize(
            topic_arg,
            max_results=args.max_results,
            out_file=args.out,
            insecure_ssl=bool(args.insecure_ssl or os.getenv("RA_INSECURE_SSL") == "1"),
        )
        _safe_print_preview(md, 800)

    asyncio.run(_main())
