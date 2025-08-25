#Streamable HTTP.

'''
If you pass an HTTP URL like https://mcp.deepwiki.com/mcp, it uses Streamable HTTP automatically.
SSE (/sse) would require an SSE-capable client/transport.
stdio has no URL; you'd spawn a local process and talk via stdin/stdout with a different client.
'''

import asyncio
import json
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from fastmcp import Client as MCPClient
import google.generativeai as genai

# Defaults; override via CLI
# Prefer the public DeepWiki MCP endpoint if no env is set.
DEFAULT_DEEPWIKI_URL = os.getenv("DEEPWIKI_URL", "https://mcp.deepwiki.com/mcp")


def _extract_text(res_obj) -> str:
    """Normalize FastMCP result shapes to a text string."""
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


def _safe_preview(s: str, n: int = 800) -> str:
    return s[:n]


async def query_deepwiki(
    server_url: str,
    repo: str,
    question: str,
    topic: str | None = None,
    model: str | None = None,
    out_file: str | None = None,
) -> str:
    """
    - Uses DeepWiki MCP tools to gather repo docs and answer a question.
    - Uses Gemini to produce a clear, grounded explanation (Markdown).
    - Optionally saves to out_file and returns the markdown string.
    """
    load_dotenv()

    # 1) Gather structure (TOC)
    client = MCPClient(server_url)
    async with client:
        # Hosted DeepWiki expects repoName; include both for compatibility
        toc_obj: Any = await client.call_tool("read_wiki_structure", {"repo": repo, "repoName": repo})
        toc_txt = _extract_text(toc_obj)
        toc: Any
        try:
            toc = json.loads(toc_txt) if toc_txt.strip().startswith(("[", "{")) else toc_txt
        except Exception:
            toc = toc_txt

        # 2) Optionally fetch specific topic content for grounding
        page: Dict[str, Any] | None = None
        if topic:
            # Include both legacy and hosted param names
            page_obj = await client.call_tool(
                "read_wiki_contents",
                {"repo": repo, "repoName": repo, "topic": topic, "topicName": topic},
            )
            page_txt = _extract_text(page_obj)
            try:
                page = json.loads(page_txt) if page_txt.strip().startswith(("{", "[")) else {"content": page_txt}
            except Exception:
                page = {"content": page_txt}

        # 3) Ask DeepWiki its own grounded answer
        # Include both legacy and hosted param names
        ask_obj = await client.call_tool(
            "ask_question",
            {"repo": repo, "repoName": repo, "question": question, "questionText": question},
        )
        ask_txt = _extract_text(ask_obj)

    # 4) Build a summarization prompt for Gemini
    grounding = {
        "repo": repo,
        "question": question,
        "toc": toc,
        "topic": topic,
        "page": page or {},
        "deepwiki_answer": ask_txt,
    }
    prompt = (
        "You are a precise software explainer. Read the JSON grounding that contains a GitHub repo's docs "
        "structure, optional page content, and an AI-grounded answer from the DeepWiki MCP server. "
        "Write a concise, accurate, developer-focused explanation in Markdown that answers the user's question.\n\n"
        "JSON grounding:\n" + json.dumps(grounding, indent=2) + "\n\n"
        "Instructions:\n"
        "- Be factual; don't invent APIs.\n"
        "- Use short sections with headings and bullet points.\n"
        "- If code snippets are relevant, include minimal runnable examples.\n"
        "- End with a References section linking to the most relevant doc pages or repo files.\n"
    )

    # 5) Generate explanation with Gemini
    api_key = os.getenv("GOOGLE_API_KEY")
    selected_model = model or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"

    try:
        mdl = genai.GenerativeModel(selected_model, system_instruction=(
            "You are a precise, pragmatic technical writer for developers. Output must be Markdown."
        ))
        answer_md = mdl.generate_content(prompt).text or ""
    except Exception:
        # Fallback minimal summary so the flow still succeeds
        answer_md = (
            f"# Explanation for: {question}\n\n"
            f"This is a brief, local fallback summary grounded in available DeepWiki data for `{repo}`.\n\n"
            "## DeepWiki Answer (raw)\n"
            f"{_safe_preview(ask_txt, 1200)}\n\n"
            "## Notes\n- Full LLM summarization unavailable (e.g., quota).\n"
        )

    # 6) Optionally save
    if out_file:
        from pathlib import Path
        Path(out_file).write_text(answer_md, encoding="utf-8")

    return answer_md


async def _main():
    import argparse

    parser = argparse.ArgumentParser(description="DeepWiki Assistant — Ask questions about a GitHub repo")
    parser.add_argument("--server-url", type=str, default=DEFAULT_DEEPWIKI_URL, help="DeepWiki MCP server URL (…/mcp)")
    parser.add_argument("--repo", type=str, default=None, help="GitHub repo in 'owner/name' format")
    parser.add_argument("--question", type=str, default=None, help="Your question about the repo")
    parser.add_argument("--topic", type=str, default=None, help="Optional topic/slug from wiki structure to ground on")
    parser.add_argument("--model", type=str, default=None, help="Gemini model (default: gemini-1.5-flash)")
    parser.add_argument("--out", type=str, default="deepwiki_answer.md", help="Output markdown file path")
    args = parser.parse_args()

    # Interactive prompts for missing values
    repo = args.repo or input("Enter repo (owner/name): ").strip()
    if not repo:
        raise SystemExit("Repo is required.")

    question = args.question or input("Enter your question: ").strip()
    if not question:
        raise SystemExit("Question is required.")

    # Normalize topic; avoid prompting if non-interactive
    topic = args.topic
    if topic in ("", "none", "null", "-"):
        topic = None
    if topic is None:
        try:
            if sys.stdin is None or not sys.stdin.isatty():
                topic = None
            else:
                t = input("Topic slug (optional, press Enter to skip): ").strip()
                topic = t or None
        except Exception:
            topic = None

    md = await query_deepwiki(
        server_url=args.server_url,
        repo=repo,
        question=question,
        topic=topic,
        model=args.model,
        out_file=args.out,
    )

    # Print preview
    prev = _safe_preview(md, 800)
    try:
        print(prev, "\n...\n")
    except UnicodeEncodeError:
        print(prev.encode("cp1252", errors="replace").decode("cp1252"), "\n...\n")


if __name__ == "__main__":
    asyncio.run(_main())
