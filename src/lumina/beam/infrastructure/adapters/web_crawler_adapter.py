"""
Web Crawler Adapter — Infrastructure implementation of ContentCrawlerPort

Uses httpx for async HTTP requests and BeautifulSoup for HTML parsing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup


class WebCrawlerAdapter:
    """Implements ContentCrawlerPort using httpx + BeautifulSoup.

    Crawls web pages, extracts text content, and parses XML sitemaps.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_redirects: int = 5,
        user_agent: str = "LUMINA-BEAM/1.0 (Content Optimisation Crawler)",
    ) -> None:
        self._timeout = timeout
        self._max_redirects = max_redirects
        self._user_agent = user_agent

    async def crawl_url(self, url: str) -> tuple[str, str]:
        """Crawl a URL and extract its title and text content.

        Args:
            url: The URL to crawl.

        Returns:
            A tuple of (page title, extracted text content).

        Raises:
            httpx.HTTPStatusError: If the server returns an error status.
            httpx.RequestError: If the request fails.
        """
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            max_redirects=self._max_redirects,
            headers={"User-Agent": self._user_agent},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ("", response.text)

        soup = BeautifulSoup(response.text, "html.parser")

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        if not title:
            h1_tag = soup.find("h1")
            if h1_tag:
                title = h1_tag.get_text(strip=True)

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        if main_content is None:
            main_content = soup

        text = main_content.get_text(separator="\n", strip=True)

        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        cleaned_text = "\n\n".join(lines)

        return (title, cleaned_text)

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        """Parse a sitemap XML and return all discovered URLs.

        Supports both regular sitemaps and sitemap index files.

        Args:
            sitemap_url: URL of the sitemap XML.

        Returns:
            A list of URLs found in the sitemap.

        Raises:
            httpx.HTTPStatusError: If the server returns an error status.
        """
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            max_redirects=self._max_redirects,
            headers={"User-Agent": self._user_agent},
        ) as client:
            response = await client.get(sitemap_url)
            response.raise_for_status()

        urls: list[str] = []
        root = ET.fromstring(response.text)

        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        sitemap_tags = root.findall(f"{ns}sitemap")
        if sitemap_tags:
            sub_sitemap_urls = []
            for sitemap_tag in sitemap_tags:
                loc = sitemap_tag.find(f"{ns}loc")
                if loc is not None and loc.text:
                    sub_sitemap_urls.append(loc.text.strip())

            for sub_url in sub_sitemap_urls:
                sub_urls = await self.crawl_sitemap(sub_url)
                urls.extend(sub_urls)
        else:
            url_tags = root.findall(f"{ns}url")
            for url_tag in url_tags:
                loc = url_tag.find(f"{ns}loc")
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())

        return urls
