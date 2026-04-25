"""Web search tool — search the internet for information.

Uses DuckDuckGo HTML search as a free, no-API-key search backend.
Parses search results from the response and returns structured output.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

import httpx
import structlog
from pydantic import BaseModel, Field

from app.models.mcp import ToolCategory
from app.tools.base import ShadowLinkTool

logger = structlog.get_logger("tools.web_search")


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum number of results")


class WebSearchTool(ShadowLinkTool):
    """Search the web for current information using DuckDuckGo."""

    name: str = "web_search"
    description: str = "Search the web for current information. Returns titles, snippets, and URLs."
    args_schema: type[BaseModel] = WebSearchInput
    category: ToolCategory = ToolCategory.SEARCH

    def _run(self, query: str, max_results: int = 5) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, query: str, max_results: int = 5) -> str:
        """Execute web search via DuckDuckGo HTML."""
        try:
            results = await self._search_ddg(query, max_results)
            if not results:
                return f"No results found for: {query}"

            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['url']}")
                lines.append(f"   {r['snippet']}\n")
            return "\n".join(lines)
        except Exception as exc:
            await logger.aerror("web_search_error", query=query, error=str(exc))
            return f"Search failed: {exc}"

    async def _search_ddg(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Search DuckDuckGo HTML and parse results."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
            )
            resp.raise_for_status()
            return self._parse_ddg_html(resp.text, max_results)

    @staticmethod
    def _parse_ddg_html(html: str, max_results: int) -> list[dict[str, str]]:
        """Parse DuckDuckGo HTML search results."""
        results: list[dict[str, str]] = []

        # Match result blocks
        snippets = re.findall(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.+?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</span>',
            html,
            re.DOTALL,
        )

        for url_raw, title_raw, snippet_raw in snippets[:max_results]:
            # Clean HTML tags
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()

            # DuckDuckGo wraps URLs in a redirect — extract real URL
            url = url_raw
            if "uddg=" in url:
                match = re.search(r"uddg=([^&]+)", url)
                if match:
                    url = unquote(match.group(1))

            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet})

        return results
