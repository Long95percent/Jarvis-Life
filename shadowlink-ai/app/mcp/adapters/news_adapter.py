"""Local news adapter — fetches headlines from public RSS feeds.

Uses RSS so no API key is required (unlike NewsAPI). User can add/remove
feeds via user_settings in a later iteration; for now a small curated
set covers the demo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from xml.etree import ElementTree

import httpx
import structlog

logger = structlog.get_logger("mcp.news")

# Curated feeds — broad mix, all English-safe + CN-safe
_DEFAULT_FEEDS: list[dict[str, str]] = [
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "人民日报海外", "url": "http://www.people.com.cn/rss/world.xml"},
]


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: str | None = None
    summary: str | None = None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


async def fetch_news(
    feeds: list[dict[str, str]] | None = None,
    limit: int = 10,
) -> list[NewsItem]:
    """Return up to `limit` news items aggregated across feeds.

    Failures on individual feeds are logged but don't raise.
    """
    sources = feeds or _DEFAULT_FEEDS
    items: list[NewsItem] = []

    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        for feed in sources:
            try:
                resp = await client.get(feed["url"])
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.text)

                def _find_first(parent, *names):
                    """Return the first matching Element (or None).

                    ElementTree.Element has a deprecated truthiness based on
                    child count, so we must compare against None explicitly.
                    """
                    for name in names:
                        el = parent.find(name)
                        if el is not None:
                            return el
                    return None

                # Handle both RSS 2.0 and Atom
                for node in root.iter():
                    tag = node.tag.split("}")[-1]
                    if tag != "item" and tag != "entry":
                        continue
                    title_el = _find_first(
                        node, "title", "{http://www.w3.org/2005/Atom}title"
                    )
                    link_el = _find_first(
                        node, "link", "{http://www.w3.org/2005/Atom}link"
                    )
                    desc_el = _find_first(
                        node,
                        "description",
                        "{http://www.w3.org/2005/Atom}summary",
                    )
                    pub_el = _find_first(
                        node, "pubDate", "{http://www.w3.org/2005/Atom}updated"
                    )

                    if title_el is None:
                        continue
                    title = _strip_html(title_el.text or "")[:200]
                    link = ""
                    if link_el is not None:
                        link = link_el.text or link_el.get("href") or ""
                    summary = _strip_html(desc_el.text or "")[:280] if desc_el is not None else None
                    published = pub_el.text if pub_el is not None else None
                    if title:
                        items.append(NewsItem(
                            title=title, link=link, source=feed["name"],
                            published=published, summary=summary,
                        ))
                        if len(items) >= limit * len(sources):
                            break
            except Exception as exc:
                logger.warning("mcp.news.fetch_failed", feed=feed["name"], error=str(exc))

    return items[:limit]
