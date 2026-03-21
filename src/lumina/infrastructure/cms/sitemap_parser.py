"""
Universal Sitemap Parser — Extracts URLs from XML sitemaps.

Architectural Intent:
- Handles standard XML sitemaps (sitemap.xml) and sitemap index files
- Supports gzip-compressed sitemaps
- URL filtering via include/exclude regex patterns
- Returns structured SitemapEntry objects with metadata (lastmod, changefreq, priority)
"""

from __future__ import annotations

import gzip
import logging
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

import httpx

logger = logging.getLogger("lumina.cms.sitemap")

# Standard XML sitemap namespace
_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass(frozen=True)
class SitemapEntry:
    """A single URL entry from a sitemap.

    Attributes:
        url: The absolute URL.
        lastmod: Last modification date string (ISO 8601), if provided.
        changefreq: Suggested crawl frequency (always, hourly, daily, etc.).
        priority: Crawl priority between 0.0 and 1.0.
    """

    url: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


class SitemapParser:
    """Parses XML sitemaps and sitemap index files.

    Attributes:
        timeout: HTTP timeout in seconds.
        include_patterns: Only URLs matching any of these regexes are returned.
        exclude_patterns: URLs matching any of these regexes are filtered out.
    """

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._include_res = [re.compile(p) for p in (include_patterns or [])]
        self._exclude_res = [re.compile(p) for p in (exclude_patterns or [])]

    async def parse(self, sitemap_url: str) -> list[SitemapEntry]:
        """Parse a sitemap URL, handling both regular sitemaps and sitemap indexes.

        If the document is a sitemap index, each referenced child sitemap is
        fetched and parsed recursively.
        """
        xml_bytes = await self._fetch(sitemap_url)
        root = ElementTree.fromstring(xml_bytes)
        tag = _strip_ns(root.tag)

        if tag == "sitemapindex":
            return await self._parse_index(root)
        elif tag == "urlset":
            return self._parse_urlset(root)
        else:
            logger.warning("Unknown sitemap root element: %s", root.tag)
            return []

    # -- Internal parsing methods ----------------------------------------------

    async def _parse_index(self, root: ElementTree.Element) -> list[SitemapEntry]:
        """Parse a sitemap index file and recursively fetch child sitemaps."""
        child_urls: list[str] = []
        for sitemap_el in root.findall("sm:sitemap", _SITEMAP_NS):
            loc_el = sitemap_el.find("sm:loc", _SITEMAP_NS)
            if loc_el is not None and loc_el.text:
                child_urls.append(loc_el.text.strip())

        # Also try without namespace (some sitemaps omit the namespace)
        if not child_urls:
            for sitemap_el in root.findall("sitemap"):
                loc_el = sitemap_el.find("loc")
                if loc_el is not None and loc_el.text:
                    child_urls.append(loc_el.text.strip())

        all_entries: list[SitemapEntry] = []
        for child_url in child_urls:
            try:
                entries = await self.parse(child_url)
                all_entries.extend(entries)
            except Exception as exc:
                logger.error("Failed to parse child sitemap %s: %s", child_url, exc)

        return all_entries

    def _parse_urlset(self, root: ElementTree.Element) -> list[SitemapEntry]:
        """Parse a <urlset> element and extract URL entries."""
        entries: list[SitemapEntry] = []

        # Try namespaced first, then bare
        url_elements = root.findall("sm:url", _SITEMAP_NS)
        if not url_elements:
            url_elements = root.findall("url")

        for url_el in url_elements:
            loc_el = url_el.find("sm:loc", _SITEMAP_NS)
            if loc_el is None:
                loc_el = url_el.find("loc")
            if loc_el is None or not loc_el.text:
                continue

            url = loc_el.text.strip()

            # Apply filters
            if not self._matches_filters(url):
                continue

            lastmod_el = url_el.find("sm:lastmod", _SITEMAP_NS)
            if lastmod_el is None:
                lastmod_el = url_el.find("lastmod")
            changefreq_el = url_el.find("sm:changefreq", _SITEMAP_NS)
            if changefreq_el is None:
                changefreq_el = url_el.find("changefreq")
            priority_el = url_el.find("sm:priority", _SITEMAP_NS)
            if priority_el is None:
                priority_el = url_el.find("priority")

            entry = SitemapEntry(
                url=url,
                lastmod=lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None,
                changefreq=changefreq_el.text.strip() if changefreq_el is not None and changefreq_el.text else None,
                priority=float(priority_el.text.strip()) if priority_el is not None and priority_el.text else None,
            )
            entries.append(entry)

        return entries

    # -- Fetching & decompression ---------------------------------------------

    async def _fetch(self, url: str) -> bytes:
        """Fetch a sitemap URL, handling gzip compression transparently."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        # Handle gzip content (either by Content-Encoding or .gz extension)
        if url.endswith(".gz") or response.headers.get("content-encoding") == "gzip":
            try:
                content = gzip.decompress(content)
            except Exception:
                # If decompression fails, try using the raw bytes
                # (it might already have been decompressed by httpx)
                pass

        return content

    # -- Filtering -------------------------------------------------------------

    def _matches_filters(self, url: str) -> bool:
        """Check whether a URL passes the include/exclude filter lists."""
        if self._exclude_res:
            for pattern in self._exclude_res:
                if pattern.search(url):
                    return False

        if self._include_res:
            for pattern in self._include_res:
                if pattern.search(url):
                    return True
            return False  # include patterns specified but none matched

        return True


def _strip_ns(tag: str) -> str:
    """Strip the XML namespace from a tag name."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag
