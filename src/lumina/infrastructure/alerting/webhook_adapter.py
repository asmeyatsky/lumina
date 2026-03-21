"""
Webhook Alert Adapter — Sends JSON payloads to a generic webhook endpoint.

Architectural Intent:
- Implements AlertPort for arbitrary third-party integrations
- HMAC-SHA256 signature in X-Signature header for payload verification
- Exponential-backoff retry logic (3 attempts) for transient failures
- Configurable timeout
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, UTC
from typing import Any

import httpx

logger = logging.getLogger("lumina.alerting.webhook")

_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 1.0
_BACKOFF_MULTIPLIER = 2.0


class WebhookAlertAdapter:
    """AlertPort implementation that POSTs JSON to a webhook URL.

    Attributes:
        url: Target webhook URL.
        secret: HMAC-SHA256 secret for signing payloads.
        headers: Extra headers to include on every request.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        url: str,
        *,
        secret: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._url = url
        self._secret = secret
        self._extra_headers = headers or {}
        self._timeout = timeout

    # -- AlertPort interface ---------------------------------------------------

    async def send_citation_drop_alert(
        self,
        brand_id: str,
        engine: str,
        prompt_text: str,
        previous_position: str,
    ) -> None:
        payload = {
            "alert_type": "citation_drop",
            "brand_id": brand_id,
            "engine": engine,
            "prompt_text": prompt_text,
            "previous_position": previous_position,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._post_with_retry(payload)

    async def send_hallucination_alert(
        self,
        brand_id: str,
        engine: str,
        claim: str,
        prompt_text: str,
    ) -> None:
        payload = {
            "alert_type": "hallucination",
            "brand_id": brand_id,
            "engine": engine,
            "claim": claim,
            "prompt_text": prompt_text,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._post_with_retry(payload)

    async def send_competitor_surge_alert(
        self,
        brand_id: str,
        competitor_id: str,
        engine: str,
        surge_percentage: float,
    ) -> None:
        payload = {
            "alert_type": "competitor_surge",
            "brand_id": brand_id,
            "competitor_id": competitor_id,
            "engine": engine,
            "surge_percentage": surge_percentage,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._post_with_retry(payload)

    # -- Internal helpers ------------------------------------------------------

    def _sign(self, body: bytes) -> str:
        """Compute HMAC-SHA256 hex digest of the request body."""
        return hmac.new(
            self._secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

    async def _post_with_retry(self, payload: dict[str, Any]) -> None:
        """POST the payload with up to ``_MAX_RETRIES`` attempts using exponential backoff."""
        body = json.dumps(payload, default=str).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        if self._secret:
            headers["X-Signature"] = self._sign(body)

        import asyncio

        last_exc: Exception | None = None
        backoff = _INITIAL_BACKOFF_SECONDS

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(self._url, content=body, headers=headers)
                    if response.status_code < 400:
                        logger.info(
                            "Webhook delivered on attempt %d: %s", attempt, payload.get("alert_type")
                        )
                        return
                    # Treat 4xx as non-retryable
                    if 400 <= response.status_code < 500:
                        logger.error(
                            "Webhook returned client error %d (not retrying): %s",
                            response.status_code,
                            response.text,
                        )
                        response.raise_for_status()
                    # 5xx — retryable
                    last_exc = httpx.HTTPStatusError(
                        message=f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    logger.warning(
                        "Webhook attempt %d/%d returned %d — retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        response.status_code,
                        backoff,
                    )
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Webhook attempt %d/%d failed (%s) — retrying in %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    backoff,
                )

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(backoff)
                backoff *= _BACKOFF_MULTIPLIER

        logger.error("Webhook delivery failed after %d attempts", _MAX_RETRIES)
        if last_exc is not None:
            raise last_exc
