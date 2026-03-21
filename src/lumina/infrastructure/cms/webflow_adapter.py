"""
Webflow Adapter — Crawls content via the Webflow CMS API v2.

Architectural Intent:
- Implements ContentCrawlerPort so BEAM can ingest Webflow CMS content
- Uses Webflow's CMS API v2 with bearer-token authentication
- Built-in rate limiter respecting Webflow's 60 req/min limit
- Extracts rich text fields from CMS collection items
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from html import unescape
from typing import Any

import httpx

logger = logging.getLogger("lumina.cms.webflow")

_WEBFLOW_API_BASE = "https://api.webflow.com/v2"


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to produce plain text."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class _WebflowRateLimiter:
    """Token-bucket rate limiter for the Webflow API (60 requests per minute)."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        while True:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < self._window]
            if len(self._timestamps) < self._max_requests:
                self._timestamps.append(now)
                return
            # Wait until the oldest entry expires
            wait_time = self._window - (now - self._timestamps[0]) + 0.1
            logger.debug("Webflow rate limit reached — sleeping %.1fs", wait_time)
            await asyncio.sleep(wait_time)


class WebflowAdapter:
    """ContentCrawlerPort implementation for Webflow CMS sites.

    Attributes:
        api_token: Webflow API bearer token.
        site_id: Webflow site identifier.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_token: str,
        site_id: str,
        *,
        timeout: float = 15.0,
    ) -> None:
        self._api_token = api_token
        self._site_id = site_id
        self._timeout = timeout
        self._rate_limiter = _WebflowRateLimiter()

    # -- ContentCrawlerPort interface ------------------------------------------

    async def crawl_url(self, url: str) -> tuple[str, str]:
        """Crawl a Webflow page by URL.

        Searches across all collections for an item whose slug matches the URL path.
        Falls back to direct HTML fetch if no match is found.
        """
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        collections = await self.list_collections()
        for collection in collections:
            collection_id = collection["id"]
            items = await self.get_collection_items(collection_id)
            for item in items:
                if item.get("slug") == slug:
                    title = item.get("name", "")
                    content = self._extract_rich_text(item)
                    return title, content

        # Fallback: direct fetch
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = _strip_html(title_match.group(1)) if title_match else ""
            body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.IGNORECASE | re.DOTALL)
            body_text = _strip_html(body_match.group(1)) if body_match else _strip_html(html)
            return title, body_text

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        """Parse the sitemap and return discovered URLs."""
        from lumina.infrastructure.cms.sitemap_parser import SitemapParser

        parser = SitemapParser(timeout=self._timeout)
        entries = await parser.parse(sitemap_url)
        return [entry.url for entry in entries]

    # -- Webflow-specific methods ---------------------------------------------

    async def list_collections(self) -> list[dict[str, Any]]:
        """List all CMS collections for the configured site."""
        url = f"{_WEBFLOW_API_BASE}/sites/{self._site_id}/collections"
        data = await self._api_get(url)
        return data.get("collections", [])

    async def get_collection_items(
        self,
        collection_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get items from a specific CMS collection.

        Handles pagination automatically when there are more items than ``limit``.
        """
        all_items: list[dict[str, Any]] = []
        current_offset = offset

        while True:
            url = f"{_WEBFLOW_API_BASE}/collections/{collection_id}/items"
            params: dict[str, Any] = {"limit": limit, "offset": current_offset}
            data = await self._api_get(url, params=params)

            items = data.get("items", [])
            if not items:
                break
            all_items.extend(items)

            total = data.get("pagination", {}).get("total", 0)
            current_offset += len(items)
            if current_offset >= total:
                break

        return all_items

    # -- Internal helpers ------------------------------------------------------

    async def _api_get(
        self, url: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Issue a rate-limited GET request to the Webflow API."""
        await self._rate_limiter.acquire()

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=headers, params=params or {})
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "5"))
                logger.warning("Webflow 429 — waiting %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                return await self._api_get(url, params=params)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _extract_rich_text(item: dict[str, Any]) -> str:
        """Extract and concatenate all rich-text fields from a Webflow item.

        Webflow stores rich text in field values with HTML markup.
        This method scans every string field for HTML-looking content and strips it.
        """
        text_parts: list[str] = []
        field_data = item.get("fieldData", item)

        for key, value in field_data.items():
            if key in ("_id", "slug", "name", "_archived", "_draft", "created-on", "updated-on"):
                continue
            if isinstance(value, str) and ("<" in value or len(value) > 50):
                cleaned = _strip_html(value)
                if cleaned:
                    text_parts.append(cleaned)

        return " ".join(text_parts)
