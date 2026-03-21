"""
Slack App Integration — Interactive Slack features beyond simple webhooks.

Architectural Intent:
- Uses the Slack Web API for rich interactive capabilities
- Posts daily/weekly AVS summaries to configured channels
- Handles slash commands (/lumina-avs {brand})
- Interactive message buttons for recommendation actions
- Per-brand channel configuration
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

import httpx

logger = logging.getLogger("lumina.integrations.slack_app")

_SLACK_API_BASE = "https://slack.com/api"


class SlackAppIntegration:
    """Slack Web API integration for interactive LUMINA features.

    Attributes:
        bot_token: Slack Bot User OAuth Token (xoxb-...).
        signing_secret: Slack app signing secret for request verification.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        bot_token: str,
        *,
        signing_secret: str = "",
        timeout: float = 10.0,
    ) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._timeout = timeout
        # Channel mapping: brand_id -> Slack channel ID
        self._brand_channels: dict[str, str] = {}

    # -- Channel configuration ------------------------------------------------

    def configure_channel(self, brand_id: str, channel_id: str) -> None:
        """Map a brand to a Slack channel for summaries and alerts."""
        self._brand_channels[brand_id] = channel_id

    def get_channel(self, brand_id: str) -> str | None:
        """Get the configured Slack channel for a brand."""
        return self._brand_channels.get(brand_id)

    # -- AVS Summaries --------------------------------------------------------

    async def post_avs_summary(
        self,
        brand_id: str,
        avs_score: float,
        *,
        delta: float = 0.0,
        period: str = "daily",
        components: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Post a daily or weekly AVS summary to the brand's configured channel.

        Args:
            brand_id: The brand identifier.
            avs_score: Current AVS score.
            delta: Change from the previous period.
            period: "daily" or "weekly".
            components: Optional breakdown (pulse, graph, beam, signal).

        Returns:
            Slack API response.
        """
        channel = self._brand_channels.get(brand_id)
        if not channel:
            raise ValueError(f"No Slack channel configured for brand {brand_id}")

        trend_emoji = _trend_emoji(delta)
        period_label = "Daily" if period == "daily" else "Weekly"

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{period_label} AVS Summary — {brand_id}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*AI Visibility Score:* {avs_score:.1f} {trend_emoji} ({delta:+.1f})\n"
                        f"*Period:* {period_label}\n"
                        f"*Generated:* {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
                    ),
                },
            },
        ]

        if components:
            fields = []
            for module_name, score in components.items():
                fields.append({"type": "mrkdwn", "text": f"*{module_name.upper()}:*\n{score:.1f}"})
            blocks.append({"type": "section", "fields": fields})

        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Dashboard"},
                    "url": f"https://app.lumina.ai/brands/{brand_id}/dashboard",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Recommendations"},
                    "url": f"https://app.lumina.ai/brands/{brand_id}/recommendations",
                },
            ],
        })

        return await self._post_message(channel, blocks=blocks)

    # -- Slash command handler -------------------------------------------------

    async def handle_avs_command(self, brand_id: str) -> dict[str, Any]:
        """Handle the /lumina-avs slash command.

        Returns a response payload suitable for Slack's slash-command response URL.

        Args:
            brand_id: Brand name or ID from the command text.

        Returns:
            Slack message payload with the current AVS score information.
        """
        # In production this would query the Intelligence Engine.
        # Here we return a well-structured response that the caller can
        # populate with real data.
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*LUMINA AVS for `{brand_id}`*\n"
                            f"Use the dashboard for the latest score and trends."
                        ),
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Open Dashboard"},
                            "url": f"https://app.lumina.ai/brands/{brand_id}/dashboard",
                            "style": "primary",
                        },
                    ],
                },
            ],
        }

    # -- Interactive message handlers ------------------------------------------

    async def handle_interaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle an interactive message callback from Slack.

        Dispatches based on the action_id of the button that was clicked.

        Args:
            payload: The Slack interaction payload.

        Returns:
            Response payload (may update the original message).
        """
        actions = payload.get("actions", [])
        if not actions:
            return {"text": "No action received."}

        action = actions[0]
        action_id = action.get("action_id", "")

        if action_id == "dismiss_alert":
            return {
                "response_type": "ephemeral",
                "text": "Alert dismissed.",
                "replace_original": False,
            }
        elif action_id == "approve_recommendation":
            return {
                "response_type": "in_channel",
                "text": "Recommendation approved and scheduled for execution.",
                "replace_original": False,
            }
        elif action_id == "snooze_recommendation":
            return {
                "response_type": "ephemeral",
                "text": "Recommendation snoozed for 24 hours.",
                "replace_original": False,
            }
        else:
            return {"text": f"Unknown action: {action_id}"}

    async def post_recommendation(
        self,
        brand_id: str,
        recommendation_id: str,
        description: str,
        expected_impact: float,
        effort_level: str,
    ) -> dict[str, Any]:
        """Post an actionable recommendation to the brand's Slack channel.

        Includes Approve / Snooze buttons for interactive handling.
        """
        channel = self._brand_channels.get(brand_id)
        if not channel:
            raise ValueError(f"No Slack channel configured for brand {brand_id}")

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "New LUMINA Recommendation"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{description}*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Expected AVS Impact:*\n+{expected_impact:.1f}"},
                    {"type": "mrkdwn", "text": f"*Effort:*\n{effort_level}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "action_id": "approve_recommendation",
                        "style": "primary",
                        "value": recommendation_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Snooze"},
                        "action_id": "snooze_recommendation",
                        "value": recommendation_id,
                    },
                ],
            },
        ]

        return await self._post_message(channel, blocks=blocks)

    # -- Connection test -------------------------------------------------------

    async def test_connection(self) -> bool:
        """Validate that the bot token is valid."""
        try:
            result = await self._api_call("auth.test")
            return result.get("ok", False)
        except Exception as exc:
            logger.warning("Slack connection test failed: %s", exc)
            return False

    # -- Internal helpers ------------------------------------------------------

    async def _post_message(
        self,
        channel: str,
        *,
        text: str = "",
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Post a message to a Slack channel using chat.postMessage."""
        payload: dict[str, Any] = {"channel": channel}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
            if not text:
                # Slack requires a fallback text for notifications
                payload["text"] = "LUMINA notification"

        return await self._api_call("chat.postMessage", payload)

    async def _api_call(
        self, method: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call a Slack Web API method."""
        url = f"{_SLACK_API_BASE}/{method}"
        headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if payload:
                response = await client.post(url, headers=headers, json=payload)
            else:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


def _trend_emoji(delta: float) -> str:
    """Return a trend emoji based on the score delta."""
    if delta > 2.0:
        return "(up)"
    elif delta > 0:
        return "(slightly up)"
    elif delta < -2.0:
        return "(down)"
    elif delta < 0:
        return "(slightly down)"
    return "(stable)"
