"""
Alert Dispatcher — Routes alerts to configured channels with cooldown tracking.

Architectural Intent:
- Central routing layer between domain alert events and channel adapters
- Evaluates AlertRules to determine which channels receive each alert
- Cooldown tracking prevents alert storms (duplicate alerts within a time window)
- Fan-out to multiple channels concurrently via asyncio.gather
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from lumina.infrastructure.alerting.alert_config import (
    AlertConfig,
    AlertType,
    ChannelType,
)

logger = logging.getLogger("lumina.alerting.dispatcher")


class AlertDispatcher:
    """Routes alerts to the correct channel adapters based on configuration.

    Attributes:
        config: The AlertConfig defining rules and channels.
        adapters: Mapping from ChannelType to a concrete AlertPort adapter.
    """

    def __init__(
        self,
        config: AlertConfig,
        adapters: dict[ChannelType, Any],
    ) -> None:
        self._config = config
        self._adapters = adapters
        # Cooldown tracker: key = (alert_type, brand_id), value = monotonic time of last fire
        self._last_fired: dict[tuple[str, str], float] = {}

    # -- Public dispatch methods -----------------------------------------------

    async def dispatch_citation_drop(
        self,
        brand_id: str,
        engine: str,
        prompt_text: str,
        previous_position: str,
    ) -> None:
        channels = self._resolve_channels(AlertType.CITATION_DROP, brand_id)
        if not channels:
            return

        coros = []
        for ch in channels:
            adapter = self._adapters.get(ch)
            if adapter is None:
                continue
            coros.append(
                adapter.send_citation_drop_alert(
                    brand_id=brand_id,
                    engine=engine,
                    prompt_text=prompt_text,
                    previous_position=previous_position,
                )
            )
        await self._fan_out(coros)

    async def dispatch_hallucination(
        self,
        brand_id: str,
        engine: str,
        claim: str,
        prompt_text: str,
    ) -> None:
        channels = self._resolve_channels(AlertType.HALLUCINATION, brand_id)
        if not channels:
            return

        coros = []
        for ch in channels:
            adapter = self._adapters.get(ch)
            if adapter is None:
                continue
            coros.append(
                adapter.send_hallucination_alert(
                    brand_id=brand_id,
                    engine=engine,
                    claim=claim,
                    prompt_text=prompt_text,
                )
            )
        await self._fan_out(coros)

    async def dispatch_competitor_surge(
        self,
        brand_id: str,
        competitor_id: str,
        engine: str,
        surge_percentage: float,
    ) -> None:
        channels = self._resolve_channels(AlertType.COMPETITOR_SURGE, brand_id)
        if not channels:
            return

        coros = []
        for ch in channels:
            adapter = self._adapters.get(ch)
            if adapter is None:
                continue
            coros.append(
                adapter.send_competitor_surge_alert(
                    brand_id=brand_id,
                    competitor_id=competitor_id,
                    engine=engine,
                    surge_percentage=surge_percentage,
                )
            )
        await self._fan_out(coros)

    # -- Internal helpers ------------------------------------------------------

    def _resolve_channels(self, alert_type: AlertType, brand_id: str) -> list[ChannelType]:
        """Determine which channels should receive this alert, respecting cooldowns."""
        cooldown_key = (alert_type.value, brand_id)
        now = time.monotonic()

        for rule in self._config.rules:
            if rule.alert_type != alert_type:
                continue

            # Check cooldown
            last = self._last_fired.get(cooldown_key)
            if last is not None:
                elapsed_minutes = (now - last) / 60.0
                if elapsed_minutes < rule.cooldown_minutes:
                    logger.info(
                        "Alert %s for %s suppressed (cooldown: %.1f min remaining)",
                        alert_type.value,
                        brand_id,
                        rule.cooldown_minutes - elapsed_minutes,
                    )
                    return []

            # Record fire time and return channels
            self._last_fired[cooldown_key] = now
            return list(rule.channels)

        # No matching rule found
        logger.debug("No alert rule for %s", alert_type.value)
        return []

    @staticmethod
    async def _fan_out(coros: list[Any]) -> None:
        """Execute coroutines concurrently, logging any individual failures."""
        if not coros:
            return
        results = await asyncio.gather(*coros, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Channel delivery failed: %s", result)
