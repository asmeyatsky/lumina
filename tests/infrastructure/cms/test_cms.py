"""
Tests for the LUMINA CMS integration adapters.

Covers:
- WordPress adapter content extraction from API responses
- Webflow adapter rate limiting
- Sitemap parser URL extraction
- Sitemap parser nested sitemap handling
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lumina.infrastructure.cms.sitemap_parser import SitemapEntry, SitemapParser
from lumina.infrastructure.cms.webflow_adapter import WebflowAdapter
from lumina.infrastructure.cms.wordpress_adapter import WordPressAdapter


# =============================================================================
# WordPress Adapter Tests
# =============================================================================


class TestWordPressAdapter:
    @pytest.mark.asyncio
    async def test_extracts_content_from_api_response(self) -> None:
        """Verify WordPress adapter correctly extracts title and content from REST API."""
        adapter = WordPressAdapter("https://example.com")

        wp_response = [
            {
                "title": {"rendered": "<p>Test Post Title</p>"},
                "content": {
                    "rendered": (
                        "<p>This is the <strong>post content</strong> with "
                        '<a href="https://example.com">a link</a>.</p>'
                    )
                },
                "link": "https://example.com/test-post",
                "date": "2025-01-15T10:00:00",
                "modified": "2025-01-16T12:00:00",
            }
        ]

        async def mock_get(
            self: Any, url: str, *, params: Any = None, auth: Any = None, **kwargs: Any
        ) -> httpx.Response:
            if "/wp-json/wp/v2/posts" in url:
                return httpx.Response(
                    200,
                    json=wp_response,
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(404, request=httpx.Request("GET", url))

        with patch.object(httpx.AsyncClient, "get", mock_get):
            title, content = await adapter.crawl_url("https://example.com/test-post")

        assert title == "Test Post Title"
        assert "post content" in content
        assert "a link" in content
        assert "<p>" not in content
        assert "<strong>" not in content

    @pytest.mark.asyncio
    async def test_fetch_posts_returns_structured_data(self) -> None:
        """Verify fetch_posts returns properly structured content dicts."""
        adapter = WordPressAdapter("https://example.com")

        wp_posts = [
            {
                "title": {"rendered": "First Post"},
                "content": {"rendered": "<p>Content of first post.</p>"},
                "link": "https://example.com/first-post",
                "date": "2025-01-10T08:00:00",
                "modified": "2025-01-11T09:00:00",
            },
            {
                "title": {"rendered": "Second Post"},
                "content": {"rendered": "<p>Content of second post.</p>"},
                "link": "https://example.com/second-post",
                "date": "2025-01-12T10:00:00",
                "modified": "2025-01-12T10:00:00",
            },
        ]

        async def mock_get(
            self: Any, url: str, *, params: Any = None, auth: Any = None, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(200, json=wp_posts, request=httpx.Request("GET", url))

        with patch.object(httpx.AsyncClient, "get", mock_get):
            posts = await adapter.fetch_posts(per_page=10, page=1)

        assert len(posts) == 2
        assert posts[0]["title"] == "First Post"
        assert posts[0]["content"] == "Content of first post."
        assert posts[0]["url"] == "https://example.com/first-post"
        assert posts[1]["title"] == "Second Post"

    @pytest.mark.asyncio
    async def test_handles_authentication(self) -> None:
        """Verify WordPress adapter passes Application Password credentials."""
        adapter = WordPressAdapter(
            "https://example.com",
            username="admin",
            password="app-password-123",
        )

        received_auth = None

        async def mock_get(
            self: Any, url: str, *, params: Any = None, auth: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal received_auth
            received_auth = auth
            return httpx.Response(
                200,
                json=[{
                    "title": {"rendered": "Auth Test"},
                    "content": {"rendered": "<p>Private content</p>"},
                    "link": "https://example.com/private",
                    "date": "2025-01-10T08:00:00",
                    "modified": "2025-01-11T09:00:00",
                }],
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            await adapter.fetch_posts()

        assert received_auth == ("admin", "app-password-123")


# =============================================================================
# Webflow Adapter Tests
# =============================================================================


class TestWebflowAdapter:
    @pytest.mark.asyncio
    async def test_handles_rate_limiting(self) -> None:
        """Verify Webflow adapter retries on 429 status."""
        adapter = WebflowAdapter(api_token="test-token", site_id="site-123")

        call_count = 0

        async def mock_get(
            self: Any, url: str, *, headers: Any = None, params: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    text="Rate limited",
                    headers={"Retry-After": "0.1"},
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(
                200,
                json={"collections": [{"id": "col-1", "displayName": "Blog"}]},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            collections = await adapter.list_collections()

        assert call_count == 2
        assert len(collections) == 1
        assert collections[0]["id"] == "col-1"

    @pytest.mark.asyncio
    async def test_extracts_rich_text_from_items(self) -> None:
        """Verify Webflow adapter extracts text from rich-text fields."""
        adapter = WebflowAdapter(api_token="test-token", site_id="site-123")

        # Mock two API calls: list_collections + get_collection_items
        api_call_index = 0

        async def mock_get(
            self: Any, url: str, *, headers: Any = None, params: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal api_call_index
            api_call_index += 1

            if "collections" in url and "items" not in url:
                return httpx.Response(
                    200,
                    json={"collections": [{"id": "col-1", "displayName": "Blog"}]},
                    request=httpx.Request("GET", url),
                )

            # Items response
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "item-1",
                            "slug": "test-page",
                            "name": "Test Page",
                            "fieldData": {
                                "body": "<h2>Welcome</h2><p>This is rich <strong>text</strong> content.</p>",
                                "summary": "A short summary of the page content.",
                            },
                        }
                    ],
                    "pagination": {"total": 1},
                },
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            title, content = await adapter.crawl_url("https://site.webflow.io/test-page")

        assert title == "Test Page"
        assert "Welcome" in content
        assert "rich" in content
        assert "text" in content
        assert "<h2>" not in content
        assert "<strong>" not in content


# =============================================================================
# Sitemap Parser Tests
# =============================================================================


class TestSitemapParser:
    @pytest.mark.asyncio
    async def test_extracts_urls_from_sitemap(self) -> None:
        """Verify sitemap parser extracts URLs with metadata."""
        parser = SitemapParser()

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
                <lastmod>2025-01-15</lastmod>
                <changefreq>weekly</changefreq>
                <priority>0.8</priority>
            </url>
            <url>
                <loc>https://example.com/page2</loc>
                <lastmod>2025-01-16</lastmod>
                <priority>0.5</priority>
            </url>
            <url>
                <loc>https://example.com/page3</loc>
            </url>
        </urlset>"""

        async def mock_get(
            self: Any, url: str, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(
                200,
                content=sitemap_xml.encode("utf-8"),
                headers={"content-type": "application/xml"},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 3
        assert entries[0].url == "https://example.com/page1"
        assert entries[0].lastmod == "2025-01-15"
        assert entries[0].changefreq == "weekly"
        assert entries[0].priority == 0.8
        assert entries[1].url == "https://example.com/page2"
        assert entries[2].url == "https://example.com/page3"
        assert entries[2].lastmod is None

    @pytest.mark.asyncio
    async def test_handles_nested_sitemaps(self) -> None:
        """Verify sitemap parser follows sitemap index files."""
        parser = SitemapParser()

        sitemap_index_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap>
                <loc>https://example.com/sitemap-posts.xml</loc>
            </sitemap>
            <sitemap>
                <loc>https://example.com/sitemap-pages.xml</loc>
            </sitemap>
        </sitemapindex>"""

        child_sitemap_posts = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/post/1</loc></url>
            <url><loc>https://example.com/post/2</loc></url>
        </urlset>"""

        child_sitemap_pages = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/about</loc></url>
        </urlset>"""

        async def mock_get(
            self: Any, url: str, **kwargs: Any
        ) -> httpx.Response:
            if "sitemap-posts" in url:
                content = child_sitemap_posts
            elif "sitemap-pages" in url:
                content = child_sitemap_pages
            else:
                content = sitemap_index_xml

            return httpx.Response(
                200,
                content=content.encode("utf-8"),
                headers={"content-type": "application/xml"},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            entries = await parser.parse("https://example.com/sitemap.xml")

        urls = [e.url for e in entries]
        assert len(urls) == 3
        assert "https://example.com/post/1" in urls
        assert "https://example.com/post/2" in urls
        assert "https://example.com/about" in urls

    @pytest.mark.asyncio
    async def test_filters_urls_by_include_pattern(self) -> None:
        """Verify sitemap parser applies include regex filters."""
        parser = SitemapParser(include_patterns=[r"/blog/"])

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/blog/post1</loc></url>
            <url><loc>https://example.com/about</loc></url>
            <url><loc>https://example.com/blog/post2</loc></url>
        </urlset>"""

        async def mock_get(
            self: Any, url: str, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(
                200,
                content=sitemap_xml.encode("utf-8"),
                headers={"content-type": "application/xml"},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 2
        assert all("/blog/" in e.url for e in entries)

    @pytest.mark.asyncio
    async def test_filters_urls_by_exclude_pattern(self) -> None:
        """Verify sitemap parser applies exclude regex filters."""
        parser = SitemapParser(exclude_patterns=[r"/tag/", r"/author/"])

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/post1</loc></url>
            <url><loc>https://example.com/tag/python</loc></url>
            <url><loc>https://example.com/author/john</loc></url>
            <url><loc>https://example.com/post2</loc></url>
        </urlset>"""

        async def mock_get(
            self: Any, url: str, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(
                200,
                content=sitemap_xml.encode("utf-8"),
                headers={"content-type": "application/xml"},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 2
        urls = [e.url for e in entries]
        assert "https://example.com/post1" in urls
        assert "https://example.com/post2" in urls
