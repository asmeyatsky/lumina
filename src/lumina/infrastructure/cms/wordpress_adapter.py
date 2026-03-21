"""
WordPress Adapter — Crawls content via the WordPress REST API v2.

Architectural Intent:
- Implements ContentCrawlerPort so BEAM can ingest WordPress content
- Uses the public REST API (wp-json/wp/v2/) with optional Application Password auth
- Strips HTML from post/page content to produce clean text
- Supports pagination for large sites
"""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin

import httpx

logger = logging.getLogger("lumina.cms.wordpress")


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to produce plain text."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


class WordPressAdapter:
    """ContentCrawlerPort implementation for WordPress sites.

    Attributes:
        base_url: Root URL of the WordPress site (e.g. https://example.com).
        username: Optional Application Password username.
        password: Optional Application Password.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        *,
        username: str = "",
        password: str = "",
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password) if username and password else None
        self._timeout = timeout

    # -- ContentCrawlerPort interface ------------------------------------------

    async def crawl_url(self, url: str) -> tuple[str, str]:
        """Crawl a single URL and return (title, content) as plain text.

        For WordPress URLs this attempts to resolve via the REST API first,
        falling back to raw HTML fetching.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Try REST API approach by searching for the URL slug
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            api_url = f"{self._base_url}/wp-json/wp/v2/posts"
            params: dict[str, Any] = {"slug": slug, "per_page": 1}
            kwargs: dict[str, Any] = {"params": params}
            if self._auth:
                kwargs["auth"] = self._auth
            response = await client.get(api_url, **kwargs)

            if response.status_code == 200:
                posts = response.json()
                if posts:
                    post = posts[0]
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = _strip_html(post.get("content", {}).get("rendered", ""))
                    return title, content

            # Fallback: try pages endpoint
            api_url = f"{self._base_url}/wp-json/wp/v2/pages"
            response = await client.get(api_url, **kwargs)
            if response.status_code == 200:
                pages = response.json()
                if pages:
                    page = pages[0]
                    title = _strip_html(page.get("title", {}).get("rendered", ""))
                    content = _strip_html(page.get("content", {}).get("rendered", ""))
                    return title, content

            # Final fallback: direct HTML fetch
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = _strip_html(title_match.group(1)) if title_match else ""
            body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.IGNORECASE | re.DOTALL)
            body_text = _strip_html(body_match.group(1)) if body_match else _strip_html(html)
            return title, body_text

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        """Parse the WordPress sitemap and return discovered URLs."""
        from lumina.infrastructure.cms.sitemap_parser import SitemapParser

        parser = SitemapParser(timeout=self._timeout)
        entries = await parser.parse(sitemap_url)
        return [entry.url for entry in entries]

    # -- WordPress-specific methods -------------------------------------------

    async def fetch_posts(
        self,
        site_url: str | None = None,
        per_page: int = 10,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch posts from the WordPress REST API.

        Returns a list of dicts with keys: title, content, url, published_at, modified_at.
        """
        base = (site_url or self._base_url).rstrip("/")
        api_url = f"{base}/wp-json/wp/v2/posts"
        params: dict[str, Any] = {"per_page": per_page, "page": page, "_embed": "true"}
        kwargs: dict[str, Any] = {"params": params}
        if self._auth:
            kwargs["auth"] = self._auth

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(api_url, **kwargs)
            response.raise_for_status()
            raw_posts = response.json()

        results: list[dict[str, Any]] = []
        for post in raw_posts:
            results.append({
                "title": _strip_html(post.get("title", {}).get("rendered", "")),
                "content": _strip_html(post.get("content", {}).get("rendered", "")),
                "url": post.get("link", ""),
                "published_at": post.get("date", ""),
                "modified_at": post.get("modified", ""),
            })
        return results

    async def fetch_pages(
        self,
        site_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from the WordPress REST API (auto-paginates).

        Returns a list of dicts with keys: title, content, url, published_at, modified_at.
        """
        base = (site_url or self._base_url).rstrip("/")
        api_url = f"{base}/wp-json/wp/v2/pages"
        all_pages: list[dict[str, Any]] = []
        page = 1

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while True:
                params: dict[str, Any] = {"per_page": 100, "page": page}
                kwargs: dict[str, Any] = {"params": params}
                if self._auth:
                    kwargs["auth"] = self._auth

                response = await client.get(api_url, **kwargs)
                if response.status_code == 400:
                    # WordPress returns 400 when page is beyond total pages
                    break
                response.raise_for_status()

                raw_pages = response.json()
                if not raw_pages:
                    break

                for wp_page in raw_pages:
                    all_pages.append({
                        "title": _strip_html(wp_page.get("title", {}).get("rendered", "")),
                        "content": _strip_html(wp_page.get("content", {}).get("rendered", "")),
                        "url": wp_page.get("link", ""),
                        "published_at": wp_page.get("date", ""),
                        "modified_at": wp_page.get("modified", ""),
                    })

                # Check if there are more pages
                total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
                if page >= total_pages:
                    break
                page += 1

        return all_pages
