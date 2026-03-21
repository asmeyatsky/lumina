"""
Google Search Console & Bing Webmaster structured data submission adapter.

Implements StructuredDataSubmissionPort using httpx for HTTP communication
with Google Search Console and Bing Webmaster APIs.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class SearchConsoleAdapter:
    """Infrastructure adapter for submitting structured data to search engine consoles.

    Implements StructuredDataSubmissionPort.

    Configuration is injected via constructor — no environment variable
    side-effects at import time.
    """

    def __init__(
        self,
        google_api_key: str,
        google_site_url: str,
        bing_api_key: str,
        bing_site_url: str,
        timeout: float = 30.0,
    ) -> None:
        self._google_api_key = google_api_key
        self._google_site_url = google_site_url
        self._bing_api_key = bing_api_key
        self._bing_site_url = bing_site_url
        self._timeout = timeout

    async def submit_to_google_search_console(self, json_ld: str) -> bool:
        """Submit a JSON-LD document to Google Search Console Indexing API.

        Uses the URL Inspection API to request indexing of pages containing
        the structured data.

        Returns True if the submission was accepted (2xx response).
        """
        url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
        payload = {
            "inspectionUrl": self._google_site_url,
            "siteUrl": self._google_site_url,
            "languageCode": "en",
        }
        headers = {
            "Authorization": f"Bearer {self._google_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code in range(200, 300):
                    logger.info(
                        "Google Search Console submission accepted for %s",
                        self._google_site_url,
                    )
                    return True
                else:
                    logger.warning(
                        "Google Search Console submission failed: %d %s",
                        response.status_code,
                        response.text,
                    )
                    return False
        except httpx.HTTPError as exc:
            logger.error(
                "Google Search Console HTTP error: %s",
                str(exc),
            )
            return False

    async def submit_to_bing_webmaster(self, json_ld: str) -> bool:
        """Submit a JSON-LD document to Bing Webmaster Tools URL Submission API.

        Returns True if the submission was accepted (2xx response).
        """
        url = "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl"
        params = {"apikey": self._bing_api_key}
        payload = {
            "siteUrl": self._bing_site_url,
            "url": self._bing_site_url,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, params=params, json=payload)
                if response.status_code in range(200, 300):
                    logger.info(
                        "Bing Webmaster submission accepted for %s",
                        self._bing_site_url,
                    )
                    return True
                else:
                    logger.warning(
                        "Bing Webmaster submission failed: %d %s",
                        response.status_code,
                        response.text,
                    )
                    return False
        except httpx.HTTPError as exc:
            logger.error(
                "Bing Webmaster HTTP error: %s",
                str(exc),
            )
            return False
