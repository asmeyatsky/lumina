"""
Tests for the LUMINA alerting system.

Covers:
- Slack adapter message formatting
- Email adapter HTML content generation
- Webhook adapter HMAC signature and retry logic
- Alert dispatcher routing, cooldown, and fan-out
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lumina.infrastructure.alerting.alert_config import (
    AlertConfig,
    AlertRule,
    AlertType,
    ChannelType,
    SlackChannelConfig,
)
from lumina.infrastructure.alerting.alert_dispatcher import AlertDispatcher
from lumina.infrastructure.alerting.email_adapter import EmailAlertAdapter
from lumina.infrastructure.alerting.slack_adapter import SlackAlertAdapter
from lumina.infrastructure.alerting.webhook_adapter import WebhookAlertAdapter


# =============================================================================
# Slack Adapter Tests
# =============================================================================


class TestSlackAlertAdapter:
    @pytest.mark.asyncio
    async def test_citation_drop_sends_blocks_with_correct_color(self) -> None:
        """Verify Slack adapter POSTs a message with red color for citation drops."""
        adapter = SlackAlertAdapter("https://hooks.slack.com/test")

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            captured_payload.update(json)
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_citation_drop_alert(
                brand_id="brand-acme",
                engine="claude",
                prompt_text="What is the best CRM?",
                previous_position="2nd",
            )

        assert "attachments" in captured_payload
        attachment = captured_payload["attachments"][0]
        assert attachment["color"] == "#E01E5A"  # red

        blocks = attachment["blocks"]
        assert blocks[0]["type"] == "header"
        assert "Citation Drop" in blocks[0]["text"]["text"]

        # Section should mention brand, engine, position
        section_text = blocks[1]["text"]["text"]
        assert "brand-acme" in section_text
        assert "claude" in section_text
        assert "2nd" in section_text

    @pytest.mark.asyncio
    async def test_hallucination_sends_blocks_with_orange_color(self) -> None:
        """Verify Slack adapter sends orange color for hallucination alerts."""
        adapter = SlackAlertAdapter("https://hooks.slack.com/test")

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            captured_payload.update(json)
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_hallucination_alert(
                brand_id="brand-acme",
                engine="gpt-4o",
                claim="Acme was founded in 1750",
                prompt_text="Tell me about Acme",
            )

        attachment = captured_payload["attachments"][0]
        assert attachment["color"] == "#E97E00"  # orange

        blocks = attachment["blocks"]
        section_text = blocks[1]["text"]["text"]
        assert "Acme was founded in 1750" in section_text
        assert "gpt-4o" in section_text

    @pytest.mark.asyncio
    async def test_competitor_surge_sends_blocks_with_yellow_color(self) -> None:
        """Verify Slack adapter sends yellow color for competitor surge alerts."""
        adapter = SlackAlertAdapter("https://hooks.slack.com/test")

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            captured_payload.update(json)
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_competitor_surge_alert(
                brand_id="brand-acme",
                competitor_id="competitor-rival",
                engine="gemini",
                surge_percentage=25.5,
            )

        attachment = captured_payload["attachments"][0]
        assert attachment["color"] == "#ECB22E"  # yellow

        blocks = attachment["blocks"]
        section_text = blocks[1]["text"]["text"]
        assert "competitor-rival" in section_text
        assert "+25.5%" in section_text


# =============================================================================
# Email Adapter Tests
# =============================================================================


class TestEmailAlertAdapter:
    @pytest.mark.asyncio
    async def test_citation_drop_builds_html_with_correct_content(self) -> None:
        """Verify email adapter sends HTML email with proper content."""
        adapter = EmailAlertAdapter(
            api_key="test-key",
            from_address="alerts@lumina.ai",
            recipients=["user@example.com"],
        )

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, json: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            captured_payload.update(json or {})
            return httpx.Response(202, text="accepted")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_citation_drop_alert(
                brand_id="brand-acme",
                engine="claude",
                prompt_text="What is the best CRM?",
                previous_position="2nd",
            )

        # Verify email structure
        assert captured_payload["subject"] == "[LUMINA] Citation Drop — brand-acme"
        assert captured_payload["from"]["email"] == "alerts@lumina.ai"
        assert captured_payload["personalizations"][0]["to"][0]["email"] == "user@example.com"

        html = captured_payload["content"][0]["value"]
        assert "Citation Drop Detected" in html
        assert "brand-acme" in html
        assert "claude" in html
        assert "2nd" in html
        assert "Unsubscribe" in html

    @pytest.mark.asyncio
    async def test_hallucination_builds_html_with_claim(self) -> None:
        """Verify hallucination email includes the incorrect claim."""
        adapter = EmailAlertAdapter(
            api_key="test-key",
            from_address="alerts@lumina.ai",
            recipients=["user@example.com", "admin@example.com"],
        )

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, json: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            captured_payload.update(json or {})
            return httpx.Response(202, text="accepted")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_hallucination_alert(
                brand_id="brand-acme",
                engine="gpt-4o",
                claim="Acme was founded in 1750",
                prompt_text="Tell me about Acme",
            )

        html = captured_payload["content"][0]["value"]
        assert "Hallucination Detected" in html
        assert "Acme was founded in 1750" in html
        # Multiple recipients
        recipients = captured_payload["personalizations"][0]["to"]
        assert len(recipients) == 2

    @pytest.mark.asyncio
    async def test_rate_limiter_suppresses_flood(self) -> None:
        """Verify rate limiter prevents email floods."""
        adapter = EmailAlertAdapter(
            api_key="test-key",
            from_address="alerts@lumina.ai",
            recipients=["user@example.com"],
            max_sends_per_hour=2,
        )

        send_count = 0

        async def mock_post(
            self: Any, url: str, *, json: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal send_count
            send_count += 1
            return httpx.Response(202, text="accepted")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            for _ in range(5):
                await adapter.send_citation_drop_alert(
                    brand_id="brand-acme",
                    engine="claude",
                    prompt_text="Test",
                    previous_position="1st",
                )

        # Only 2 should have actually sent
        assert send_count == 2


# =============================================================================
# Webhook Adapter Tests
# =============================================================================


class TestWebhookAlertAdapter:
    @pytest.mark.asyncio
    async def test_includes_hmac_signature(self) -> None:
        """Verify webhook adapter includes correct HMAC-SHA256 signature."""
        secret = "my-webhook-secret"
        adapter = WebhookAlertAdapter("https://example.com/hook", secret=secret)

        captured_headers: dict[str, str] = {}
        captured_body: bytes = b""

        async def mock_post(
            self: Any, url: str, *, content: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal captured_headers, captured_body
            captured_headers = dict(headers or {})
            captured_body = content
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_citation_drop_alert(
                brand_id="brand-acme",
                engine="claude",
                prompt_text="Test prompt",
                previous_position="3rd",
            )

        # Verify signature
        assert "X-Signature" in captured_headers
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            captured_body,
            hashlib.sha256,
        ).hexdigest()
        assert captured_headers["X-Signature"] == expected_sig

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self) -> None:
        """Verify webhook adapter retries on 5xx errors."""
        adapter = WebhookAlertAdapter("https://example.com/hook")

        call_count = 0

        async def mock_post(
            self: Any, url: str, *, content: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", url))
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await adapter.send_citation_drop_alert(
                    brand_id="brand-acme",
                    engine="claude",
                    prompt_text="Test",
                    previous_position="1st",
                )

        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """Verify webhook adapter raises after exhausting retries."""
        adapter = WebhookAlertAdapter("https://example.com/hook")

        async def mock_post(
            self: Any, url: str, *, content: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", url))

        with patch.object(httpx.AsyncClient, "post", mock_post):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(httpx.HTTPStatusError):
                    await adapter.send_citation_drop_alert(
                        brand_id="brand-acme",
                        engine="claude",
                        prompt_text="Test",
                        previous_position="1st",
                    )

    @pytest.mark.asyncio
    async def test_no_signature_when_no_secret(self) -> None:
        """Verify no X-Signature header when secret is empty."""
        adapter = WebhookAlertAdapter("https://example.com/hook", secret="")

        captured_headers: dict[str, str] = {}

        async def mock_post(
            self: Any, url: str, *, content: Any = None, headers: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal captured_headers
            captured_headers = dict(headers or {})
            return httpx.Response(200, text="ok")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            await adapter.send_citation_drop_alert(
                brand_id="brand-acme",
                engine="claude",
                prompt_text="Test",
                previous_position="1st",
            )

        assert "X-Signature" not in captured_headers


# =============================================================================
# Alert Dispatcher Tests
# =============================================================================


class _MockAdapter:
    """Mock adapter that records calls for assertion."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._should_fail = should_fail

    async def send_citation_drop_alert(self, **kwargs: Any) -> None:
        self.calls.append(("citation_drop", kwargs))
        if self._should_fail:
            raise RuntimeError("Mock failure")

    async def send_hallucination_alert(self, **kwargs: Any) -> None:
        self.calls.append(("hallucination", kwargs))
        if self._should_fail:
            raise RuntimeError("Mock failure")

    async def send_competitor_surge_alert(self, **kwargs: Any) -> None:
        self.calls.append(("competitor_surge", kwargs))
        if self._should_fail:
            raise RuntimeError("Mock failure")


class TestAlertDispatcher:
    def _make_config(self, cooldown_minutes: int = 30) -> AlertConfig:
        return AlertConfig(
            brand_id="brand-acme",
            rules=[
                AlertRule(
                    alert_type=AlertType.CITATION_DROP,
                    channels=(ChannelType.SLACK, ChannelType.EMAIL),
                    cooldown_minutes=cooldown_minutes,
                ),
                AlertRule(
                    alert_type=AlertType.HALLUCINATION,
                    channels=(ChannelType.SLACK,),
                    cooldown_minutes=cooldown_minutes,
                ),
                AlertRule(
                    alert_type=AlertType.COMPETITOR_SURGE,
                    channels=(ChannelType.WEBHOOK,),
                    cooldown_minutes=cooldown_minutes,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_routes_to_correct_channels(self) -> None:
        """Verify dispatcher sends citation drop to both Slack and Email."""
        config = self._make_config()
        slack = _MockAdapter()
        email = _MockAdapter()
        webhook = _MockAdapter()

        dispatcher = AlertDispatcher(
            config=config,
            adapters={
                ChannelType.SLACK: slack,
                ChannelType.EMAIL: email,
                ChannelType.WEBHOOK: webhook,
            },
        )

        await dispatcher.dispatch_citation_drop(
            brand_id="brand-acme",
            engine="claude",
            prompt_text="Test prompt",
            previous_position="2nd",
        )

        assert len(slack.calls) == 1
        assert slack.calls[0][0] == "citation_drop"
        assert len(email.calls) == 1
        assert email.calls[0][0] == "citation_drop"
        assert len(webhook.calls) == 0  # not in the rule for citation_drop

    @pytest.mark.asyncio
    async def test_routes_competitor_surge_to_webhook(self) -> None:
        """Verify competitor surge routes to webhook channel only."""
        config = self._make_config()
        slack = _MockAdapter()
        webhook = _MockAdapter()

        dispatcher = AlertDispatcher(
            config=config,
            adapters={
                ChannelType.SLACK: slack,
                ChannelType.WEBHOOK: webhook,
            },
        )

        await dispatcher.dispatch_competitor_surge(
            brand_id="brand-acme",
            competitor_id="competitor-rival",
            engine="gemini",
            surge_percentage=30.0,
        )

        assert len(slack.calls) == 0
        assert len(webhook.calls) == 1

    @pytest.mark.asyncio
    async def test_respects_cooldown(self) -> None:
        """Verify dispatcher suppresses duplicate alerts within cooldown window."""
        config = self._make_config(cooldown_minutes=60)
        slack = _MockAdapter()

        dispatcher = AlertDispatcher(
            config=config,
            adapters={ChannelType.SLACK: slack},
        )

        # First call should go through
        await dispatcher.dispatch_hallucination(
            brand_id="brand-acme",
            engine="claude",
            claim="Incorrect claim",
            prompt_text="Prompt",
        )
        assert len(slack.calls) == 1

        # Second call should be suppressed (within cooldown)
        await dispatcher.dispatch_hallucination(
            brand_id="brand-acme",
            engine="claude",
            claim="Another claim",
            prompt_text="Prompt 2",
        )
        assert len(slack.calls) == 1  # still 1

    @pytest.mark.asyncio
    async def test_fans_out_concurrently(self) -> None:
        """Verify dispatcher sends to multiple channels concurrently."""
        config = self._make_config()
        slack = _MockAdapter()
        email = _MockAdapter()

        dispatcher = AlertDispatcher(
            config=config,
            adapters={
                ChannelType.SLACK: slack,
                ChannelType.EMAIL: email,
            },
        )

        await dispatcher.dispatch_citation_drop(
            brand_id="brand-acme",
            engine="claude",
            prompt_text="Test",
            previous_position="1st",
        )

        # Both channels should have received the alert
        assert len(slack.calls) == 1
        assert len(email.calls) == 1

    @pytest.mark.asyncio
    async def test_handles_channel_failure_gracefully(self) -> None:
        """Verify one channel failing does not prevent others from receiving alerts."""
        config = self._make_config()
        slack = _MockAdapter(should_fail=True)
        email = _MockAdapter()

        dispatcher = AlertDispatcher(
            config=config,
            adapters={
                ChannelType.SLACK: slack,
                ChannelType.EMAIL: email,
            },
        )

        # Should not raise even though Slack adapter fails
        await dispatcher.dispatch_citation_drop(
            brand_id="brand-acme",
            engine="claude",
            prompt_text="Test",
            previous_position="1st",
        )

        # Both were called; Slack failed but email succeeded
        assert len(slack.calls) == 1
        assert len(email.calls) == 1
