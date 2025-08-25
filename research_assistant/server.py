import asyncio
import datetime
from typing import List, Dict, Any
import httpx, certifi, json, ssl
from fastmcp import FastMCP
from duckduckgo_search import DDGS
import httpx
from bs4 import BeautifulSoup


mcp = FastMCP("AI Research Assistant Server")


@mcp.tool(
    name="search_web",
    description="Search the web for recent information about an AI-related topic using DuckDuckGo. Returns a list of results with title, href, and snippet.",
)
async def search_web(query: str, max_results: int = 5) -> str:
    results: List[Dict[str, Any]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results, safesearch="Moderate"):  # type: ignore[arg-type]
            # r contains: title, href, body
            results.append({
                "title": r.get("title"),
            "url": r.get("href"),
                "snippet": r.get("body"),
            })
    return json.dumps(results)

@mcp.tool(
    name="fetch_url",
    description="Fetch a URL and extract readable text content. Returns title and first N chars of text.",
)
async def fetch_url(url: str, max_chars: int = 5000, insecure: bool = False) -> str:
    """
    Fetch a URL and return structured text.
    - Uses certifi CA bundle for secure SSL by default.
    - If SSL fails, will retry with insecure=True.
    """
    verify_option = False if insecure else certifi.where()

    try:
        async with httpx.AsyncClient(timeout=20, verify=verify_option, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except ssl.SSLError as e:
        # Retry with insecure if SSL fails
        async with httpx.AsyncClient(timeout=20, verify=False, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style/noscript
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    text = " ".join(soup.get_text(" ").split())

    return json.dumps({
        "title": title,
        "text": text[:max_chars],
        "length": len(text),
    })

@mcp.resource(
    "res://about.txt",
    name="About Research Assistant",
    title="About",
    description="Information about the Research Assistant server",
    mime_type="text/plain",
)
def about_resource() -> str:
    return (
        "AI Research Assistant MCP Server\n"
        f"Last updated: {datetime.datetime.utcnow().isoformat()}Z\n"
        "Tools: search_web, fetch_url.\n"
        "Prompt: research_summarize.\n"
    )


@mcp.prompt(
    "research_summarize",
    title="Research Summarization Prompt",
    description="Prompt template for summarizing research findings with citations.",
)
def research_prompt(topic: str = "", findings_json: str = "") -> str:
    return (
        "You are a precise AI research assistant focused on AI-related topics.\n"
        "Summarize the latest information for the topic below.\n\n"
        f"Topic: {topic}\n\n"
        "Evidence (JSON array of search results and page extracts):\n"
        f"{findings_json}\n\n"
        "Instructions:\n"
        "- Produce a concise, well-structured report.\n"
        "- Use headings, bullet points, and short paragraphs.\n"
        "- Include inline citations as [n] that map to the Sources list.\n"
        "- End with a Sources section with title and URL for each source.\n"
    )


if __name__ == "__main__":
    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8010))
