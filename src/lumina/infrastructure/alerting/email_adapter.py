"""
Email Alert Adapter — Sends branded HTML emails via the SendGrid API.

Architectural Intent:
- Implements AlertPort using SendGrid's v3 mail/send endpoint
- Rich HTML templates per alert type with clean, branded design
- Token-bucket rate limiter prevents email floods
- Supports multiple recipients per alert
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("lumina.alerting.email")

_SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class _RateLimiter:
    """Simple token-bucket rate limiter to prevent email floods.

    Allows at most ``max_sends`` emails within any ``window_seconds`` window.
    """

    def __init__(self, max_sends: int = 20, window_seconds: float = 3600.0) -> None:
        self._max_sends = max_sends
        self._window = window_seconds
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        now = time.monotonic()
        # Evict expired entries
        self._timestamps = [t for t in self._timestamps if now - t < self._window]
        if len(self._timestamps) >= self._max_sends:
            return False
        self._timestamps.append(now)
        return True


class EmailAlertAdapter:
    """AlertPort implementation that sends emails through SendGrid.

    Attributes:
        api_key: SendGrid API key.
        from_address: Sender email address.
        recipients: List of recipient email addresses.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        from_address: str,
        recipients: list[str],
        *,
        timeout: float = 10.0,
        max_sends_per_hour: int = 20,
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address
        self._recipients = recipients
        self._timeout = timeout
        self._rate_limiter = _RateLimiter(max_sends=max_sends_per_hour)

    # -- AlertPort interface ---------------------------------------------------

    async def send_citation_drop_alert(
        self,
        brand_id: str,
        engine: str,
        prompt_text: str,
        previous_position: str,
    ) -> None:
        subject = f"[LUMINA] Citation Drop — {brand_id}"
        html = _render_citation_drop_html(
            brand_id=brand_id,
            engine=engine,
            prompt_text=prompt_text,
            previous_position=previous_position,
        )
        await self._send(subject=subject, html_content=html)

    async def send_hallucination_alert(
        self,
        brand_id: str,
        engine: str,
        claim: str,
        prompt_text: str,
    ) -> None:
        subject = f"[LUMINA] Hallucination Detected — {brand_id}"
        html = _render_hallucination_html(
            brand_id=brand_id,
            engine=engine,
            claim=claim,
            prompt_text=prompt_text,
        )
        await self._send(subject=subject, html_content=html)

    async def send_competitor_surge_alert(
        self,
        brand_id: str,
        competitor_id: str,
        engine: str,
        surge_percentage: float,
    ) -> None:
        subject = f"[LUMINA] Competitor Surge — {competitor_id} (+{surge_percentage:.1f}%)"
        html = _render_competitor_surge_html(
            brand_id=brand_id,
            competitor_id=competitor_id,
            engine=engine,
            surge_percentage=surge_percentage,
        )
        await self._send(subject=subject, html_content=html)

    # -- Internal helpers ------------------------------------------------------

    async def _send(self, *, subject: str, html_content: str) -> None:
        if not self._rate_limiter.allow():
            logger.warning("Email rate limit exceeded — alert suppressed: %s", subject)
            return

        personalizations = [
            {"to": [{"email": r} for r in self._recipients]}
        ]

        payload: dict[str, Any] = {
            "personalizations": personalizations,
            "from": {"email": self._from_address, "name": "LUMINA Alerts"},
            "subject": subject,
            "content": [
                {"type": "text/html", "value": html_content},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(_SENDGRID_API_URL, json=payload, headers=headers)
            if response.status_code not in (200, 202):
                logger.error(
                    "SendGrid returned %d: %s", response.status_code, response.text
                )
                response.raise_for_status()
            else:
                logger.info("Alert email sent: %s", subject)


# =============================================================================
# HTML Templates
# =============================================================================

_BASE_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }
  .container { max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .header { padding: 24px 32px; color: #ffffff; }
  .header h1 { margin: 0; font-size: 20px; font-weight: 600; }
  .body { padding: 24px 32px; color: #333333; }
  .body p { line-height: 1.6; margin: 8px 0; }
  .label { font-weight: 600; color: #555555; }
  .value { color: #111111; }
  .claim-box { background: #fff3cd; border-left: 4px solid #E97E00; padding: 12px 16px; margin: 12px 0; border-radius: 4px; }
  .footer { padding: 16px 32px; background: #fafafa; border-top: 1px solid #eeeeee; font-size: 12px; color: #999999; text-align: center; }
  .footer a { color: #666666; }
  .btn { display: inline-block; padding: 10px 20px; border-radius: 4px; text-decoration: none; font-weight: 600; font-size: 14px; margin-top: 16px; }
</style>
"""

_FOOTER = """
<div class="footer">
  <p>You are receiving this because of your LUMINA alert preferences.</p>
  <p><a href="https://app.lumina.ai/settings/notifications">Unsubscribe or manage preferences</a></p>
</div>
"""


def _render_citation_drop_html(
    *, brand_id: str, engine: str, prompt_text: str, previous_position: str
) -> str:
    return f"""<!DOCTYPE html><html><head>{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header" style="background-color: #E01E5A;">
    <h1>Citation Drop Detected</h1>
  </div>
  <div class="body">
    <p><span class="label">Brand:</span> <span class="value">{brand_id}</span></p>
    <p><span class="label">Engine:</span> <span class="value">{engine}</span></p>
    <p><span class="label">Previous Position:</span> <span class="value">{previous_position}</span></p>
    <p><span class="label">Prompt:</span> <span class="value">{prompt_text}</span></p>
    <a href="https://app.lumina.ai/brands/{brand_id}/pulse" class="btn" style="background-color: #E01E5A; color: #ffffff;">View in LUMINA</a>
  </div>
  {_FOOTER}
</div>
</body></html>"""


def _render_hallucination_html(
    *, brand_id: str, engine: str, claim: str, prompt_text: str
) -> str:
    return f"""<!DOCTYPE html><html><head>{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header" style="background-color: #E97E00;">
    <h1>Hallucination Detected</h1>
  </div>
  <div class="body">
    <p><span class="label">Brand:</span> <span class="value">{brand_id}</span></p>
    <p><span class="label">Engine:</span> <span class="value">{engine}</span></p>
    <div class="claim-box">
      <p><span class="label">Incorrect Claim:</span></p>
      <p>{claim}</p>
    </div>
    <p><span class="label">Prompt:</span> <span class="value">{prompt_text}</span></p>
    <a href="https://app.lumina.ai/brands/{brand_id}/pulse" class="btn" style="background-color: #E97E00; color: #ffffff;">View in LUMINA</a>
  </div>
  {_FOOTER}
</div>
</body></html>"""


def _render_competitor_surge_html(
    *, brand_id: str, competitor_id: str, engine: str, surge_percentage: float
) -> str:
    return f"""<!DOCTYPE html><html><head>{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header" style="background-color: #ECB22E;">
    <h1>Competitor Surge Alert</h1>
  </div>
  <div class="body">
    <p><span class="label">Brand:</span> <span class="value">{brand_id}</span></p>
    <p><span class="label">Competitor:</span> <span class="value">{competitor_id}</span></p>
    <p><span class="label">Engine:</span> <span class="value">{engine}</span></p>
    <p><span class="label">Surge:</span> <span class="value">+{surge_percentage:.1f}%</span></p>
    <a href="https://app.lumina.ai/brands/{brand_id}/pulse" class="btn" style="background-color: #ECB22E; color: #ffffff;">View in LUMINA</a>
  </div>
  {_FOOTER}
</div>
</body></html>"""
