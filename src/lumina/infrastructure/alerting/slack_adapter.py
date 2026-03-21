"""
Slack Alert Adapter — Sends rich Slack messages via incoming webhooks.

Architectural Intent:
- Implements AlertPort so the PULSE domain can fire alerts without knowing about Slack
- Uses Block Kit for rich, colour-coded messages per alert type
- Fully async via httpx
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("lumina.alerting.slack")


class SlackAlertAdapter:
    """AlertPort implementation that posts to a Slack incoming webhook.

    Each alert type renders a dedicated Block Kit message with colour coding:
      - Citation drop  -> danger (red)
      - Hallucination  -> warning (orange)
      - Competitor surge -> caution (yellow)
    """

    def __init__(self, webhook_url: str, *, timeout: float = 10.0) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout

    # -- AlertPort interface ---------------------------------------------------

    async def send_citation_drop_alert(
        self,
        brand_id: str,
        engine: str,
        prompt_text: str,
        previous_position: str,
    ) -> None:
        """Send a citation-drop alert with trend sparkline."""
        sparkline = _trend_sparkline(previous_position)
        blocks = _build_citation_drop_blocks(
            brand_id=brand_id,
            engine=engine,
            prompt_text=prompt_text,
            previous_position=previous_position,
            sparkline=sparkline,
        )
        await self._post(blocks, color="#E01E5A")  # red

    async def send_hallucination_alert(
        self,
        brand_id: str,
        engine: str,
        claim: str,
        prompt_text: str,
    ) -> None:
        """Send a hallucination alert with the incorrect claim."""
        blocks = _build_hallucination_blocks(
            brand_id=brand_id,
            engine=engine,
            claim=claim,
            prompt_text=prompt_text,
        )
        await self._post(blocks, color="#E97E00")  # orange

    async def send_competitor_surge_alert(
        self,
        brand_id: str,
        competitor_id: str,
        engine: str,
        surge_percentage: float,
    ) -> None:
        """Send a competitor-surge alert."""
        blocks = _build_competitor_surge_blocks(
            brand_id=brand_id,
            competitor_id=competitor_id,
            engine=engine,
            surge_percentage=surge_percentage,
        )
        await self._post(blocks, color="#ECB22E")  # yellow

    # -- Internal helpers ------------------------------------------------------

    async def _post(self, blocks: list[dict[str, Any]], color: str) -> None:
        """Post a message to the Slack webhook."""
        payload: dict[str, Any] = {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._webhook_url, json=payload)
            if response.status_code != 200:
                logger.error(
                    "Slack webhook returned %d: %s",
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()


# =============================================================================
# Block Kit Builders
# =============================================================================


def _trend_sparkline(previous_position: str) -> str:
    """Generate a sparkline emoji sequence to illustrate the drop trend."""
    # Use a simple visual: the previous position suggests a downward trend
    return "\u2198\ufe0f \u2b07\ufe0f"  # down-right arrow + down arrow


def _build_citation_drop_blocks(
    *,
    brand_id: str,
    engine: str,
    prompt_text: str,
    previous_position: str,
    sparkline: str,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Citation Drop Detected",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Brand:* `{brand_id}`\n"
                    f"*Engine:* {engine}\n"
                    f"*Previous position:* {previous_position} {sparkline}\n"
                    f"*Prompt:* _{prompt_text}_"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert type:*\nCitation Drop"},
                {"type": "mrkdwn", "text": f"*Severity:*\nHigh"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in LUMINA"},
                    "url": f"https://app.lumina.ai/brands/{brand_id}/pulse",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss"},
                    "action_id": "dismiss_alert",
                },
            ],
        },
    ]


def _build_hallucination_blocks(
    *,
    brand_id: str,
    engine: str,
    claim: str,
    prompt_text: str,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Hallucination Detected",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Brand:* `{brand_id}`\n"
                    f"*Engine:* {engine}\n"
                    f"*Incorrect claim:*\n> {claim}\n"
                    f"*Prompt:* _{prompt_text}_"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert type:*\nHallucination"},
                {"type": "mrkdwn", "text": f"*Severity:*\nMedium"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in LUMINA"},
                    "url": f"https://app.lumina.ai/brands/{brand_id}/pulse",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Report to Engine"},
                    "action_id": "report_hallucination",
                    "style": "danger",
                },
            ],
        },
    ]


def _build_competitor_surge_blocks(
    *,
    brand_id: str,
    competitor_id: str,
    engine: str,
    surge_percentage: float,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Competitor Surge Alert",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Brand:* `{brand_id}`\n"
                    f"*Competitor:* `{competitor_id}`\n"
                    f"*Engine:* {engine}\n"
                    f"*Surge:* +{surge_percentage:.1f}%"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert type:*\nCompetitor Surge"},
                {"type": "mrkdwn", "text": f"*Severity:*\nLow"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in LUMINA"},
                    "url": f"https://app.lumina.ai/brands/{brand_id}/pulse",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Analyse Competitor"},
                    "action_id": "analyse_competitor",
                },
            ],
        },
    ]
