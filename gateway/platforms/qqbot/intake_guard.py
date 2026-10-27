"""Single trusted raw-message consumer, before any general gateway pipeline."""
from __future__ import annotations

import asyncio
import importlib
import math
import logging

logger = logging.getLogger(__name__)


class IntakeGuard:
    """True permits ordinary intake; every configured failure closes intake.

    The operator-selected consumer is privileged code, not an observer/plugin
    broadcast. Its factory must be quick and side-effect free.
    """

    def __init__(self, adapter, configuration):
        self.enabled = configuration is not None
        self.consumer = None
        self.timeout = 5.0
        if not self.enabled:
            return
        try:
            if type(configuration) is not dict:
                raise ValueError("invalid_guard")
            factory_path = configuration["factory"]
            timeout = configuration.get("timeout_seconds", 5.0)
            if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0.05 <= timeout <= 30:
                raise ValueError("invalid_timeout")
            module, name = factory_path.split(":")
            factory = getattr(importlib.import_module(module), name)
            self.consumer = factory(adapter, configuration.get("settings", {}))
            if not callable(self.consumer):
                raise ValueError("invalid_consumer")
            self.timeout = timeout
        except Exception:
            # Never include a loader exception: it can contain operator secrets.
            self.consumer = None
            logger.warning("QQ intake guard unavailable; intake remains closed")

    async def allow(self, event_type, payload):
        if not self.enabled:
            return True
        if self.consumer is None:
            return False
        try:
            result = await asyncio.wait_for(self.consumer(event_type, payload), self.timeout)
            return result is True
        except Exception:
            # No fail-open fallback and no exception/raw-content logging.
            logger.warning("QQ intake guard processing failed; event withheld")
            return False
