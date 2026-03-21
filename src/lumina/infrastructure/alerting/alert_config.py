"""
Alert Configuration — Dataclasses for alert routing and channel setup.

Architectural Intent:
- Centralised configuration for all alert channels and routing rules
- Each brand can have independent alert rules with per-channel settings
- Configuration is loadable from environment variables or a database record
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class AlertType(str, Enum):
    """Types of alerts the system can emit."""

    CITATION_DROP = "citation_drop"
    HALLUCINATION = "hallucination"
    COMPETITOR_SURGE = "competitor_surge"


class ChannelType(str, Enum):
    """Supported notification channel types."""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class SlackChannelConfig:
    """Configuration for a Slack webhook channel."""

    webhook_url: str
    channel_name: str = "#lumina-alerts"


@dataclass(frozen=True)
class EmailChannelConfig:
    """Configuration for SendGrid email delivery."""

    recipients: tuple[str, ...]
    from_address: str = "alerts@lumina.ai"
    sendgrid_api_key: str = ""


@dataclass(frozen=True)
class WebhookChannelConfig:
    """Configuration for a generic outbound webhook."""

    url: str
    secret: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class AlertRule:
    """A single alert routing rule.

    Attributes:
        alert_type: Which alert this rule applies to.
        channels: Channel types that should receive the alert.
        threshold: Minimum magnitude before firing (e.g. drop % > 10).
        cooldown_minutes: Suppress duplicate alerts within this window.
    """

    alert_type: AlertType
    channels: tuple[ChannelType, ...]
    threshold: float = 0.0
    cooldown_minutes: int = 30


@dataclass
class AlertConfig:
    """Full alert configuration for a single brand.

    Attributes:
        brand_id: The brand this configuration belongs to.
        rules: Ordered list of alert rules.
        channels: Mapping from channel type to its concrete config.
    """

    brand_id: str
    rules: list[AlertRule] = field(default_factory=list)
    channels: dict[ChannelType, SlackChannelConfig | EmailChannelConfig | WebhookChannelConfig] = field(
        default_factory=dict
    )

    @classmethod
    def from_env(cls, brand_id: str) -> AlertConfig:
        """Build a default configuration from environment variables.

        Environment variables:
            LUMINA_SLACK_WEBHOOK_URL — Slack incoming-webhook URL
            LUMINA_SLACK_CHANNEL — Slack channel name (default #lumina-alerts)
            LUMINA_SENDGRID_API_KEY — SendGrid API key
            LUMINA_ALERT_EMAIL_RECIPIENTS — Comma-separated email addresses
            LUMINA_ALERT_EMAIL_FROM — Sender address
            LUMINA_WEBHOOK_URL — Generic webhook URL
            LUMINA_WEBHOOK_SECRET — HMAC secret for webhook signing
        """
        channels: dict[ChannelType, SlackChannelConfig | EmailChannelConfig | WebhookChannelConfig] = {}

        slack_url = os.environ.get("LUMINA_SLACK_WEBHOOK_URL", "")
        if slack_url:
            channels[ChannelType.SLACK] = SlackChannelConfig(
                webhook_url=slack_url,
                channel_name=os.environ.get("LUMINA_SLACK_CHANNEL", "#lumina-alerts"),
            )

        sendgrid_key = os.environ.get("LUMINA_SENDGRID_API_KEY", "")
        recipients_raw = os.environ.get("LUMINA_ALERT_EMAIL_RECIPIENTS", "")
        if sendgrid_key and recipients_raw:
            recipients = tuple(r.strip() for r in recipients_raw.split(",") if r.strip())
            channels[ChannelType.EMAIL] = EmailChannelConfig(
                recipients=recipients,
                from_address=os.environ.get("LUMINA_ALERT_EMAIL_FROM", "alerts@lumina.ai"),
                sendgrid_api_key=sendgrid_key,
            )

        webhook_url = os.environ.get("LUMINA_WEBHOOK_URL", "")
        if webhook_url:
            channels[ChannelType.WEBHOOK] = WebhookChannelConfig(
                url=webhook_url,
                secret=os.environ.get("LUMINA_WEBHOOK_SECRET", ""),
            )

        # Default rules: send all alert types to all configured channels
        configured_channels = tuple(channels.keys())
        rules = [
            AlertRule(
                alert_type=AlertType.CITATION_DROP,
                channels=configured_channels,
                threshold=5.0,
                cooldown_minutes=30,
            ),
            AlertRule(
                alert_type=AlertType.HALLUCINATION,
                channels=configured_channels,
                threshold=0.0,
                cooldown_minutes=60,
            ),
            AlertRule(
                alert_type=AlertType.COMPETITOR_SURGE,
                channels=configured_channels,
                threshold=10.0,
                cooldown_minutes=30,
            ),
        ]

        return cls(brand_id=brand_id, rules=rules, channels=channels)
