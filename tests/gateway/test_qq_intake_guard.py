"""Raw intake and restricted delivery invariants (user fork Issue #1)."""
import asyncio
import json
import logging
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from gateway.config import PlatformConfig
from gateway.platforms.qqbot.adapter import QQAdapter


@pytest.mark.parametrize("event_type", list(QQAdapter._INBOUND_HANDLERS))
@pytest.mark.parametrize("mode", ["disabled", "pass", "consume", "raise", "timeout", "invalid", "load_error"])
def test_guard_runs_before_every_handler_log_media_and_busy_queue(monkeypatch, caplog, event_type, mode):
    calls = []
    provider = ModuleType("test_trusted_intake_provider")

    async def consume(kind, payload):
        calls.append((kind, payload["id"]))
        if mode == "raise":
            raise RuntimeError(payload["content"])
        if mode == "timeout":
            await asyncio.Event().wait()
        return {"pass": True, "consume": False, "invalid": 1}.get(mode, False)

    provider.create = lambda adapter, settings: consume
    monkeypatch.setitem(sys.modules, provider.__name__, provider)
    guard = dict(factory=provider.__name__ + ":create", timeout_seconds=0.05)
    if mode == "load_error":
        guard["factory"] = "nonexistent_trusted_guard:create"
    extra = dict(app_id="fictitious-bot", client_secret="fictitious", dm_policy="open", group_policy="open")
    if mode != "disabled":
        extra["intake_guard"] = guard
    adapter = QQAdapter(PlatformConfig(enabled=True, extra=extra))
    # A handler is the earliest door to C2C body logs, media, STT, quoted
    # context, base queues and runner observers/plugins/busy/model/history.
    door = AsyncMock()
    monkeypatch.setattr(adapter, adapter._INBOUND_HANDLERS[event_type], door)
    adapter._active_sessions["occupied"] = True
    adapter._pending_messages["occupied"] = []
    payload = dict(id="fake-event", content="private-answer-4000",
                   attachments=[{"asr_refer_text": "private-answer-4000"}])
    with caplog.at_level(logging.DEBUG):
        asyncio.run(adapter._on_message(event_type, payload))
    admitted = mode in ("disabled", "pass")
    assert door.await_count == int(admitted)
    assert adapter._pending_messages == {"occupied": []}
    assert "private-answer-4000" not in caplog.text
    assert len(calls) == int(mode not in ("disabled", "load_error"))


@pytest.mark.parametrize("reply", [
    {"id": "real-fake-platform-id"}, {}, {"id": "local-invented"},
    {"id": "invalid platform id"}, {"error": "private-balance-12345"},
])
def test_private_delivery_uses_original_qq_transport_once_and_requires_platform_id(caplog, reply):
    requests = []

    async def transport(request):
        requests.append((request.url.path, json.loads(request.content)))
        if "error" in reply:
            return httpx.Response(403, json={"message": reply["error"]})
        return httpx.Response(200, json=reply)

    async def exercise():
        adapter = QQAdapter(PlatformConfig(enabled=True, extra=dict(app_id="fake-bot", client_secret="fake", markdown_support=False)))
        adapter._running = True
        adapter._ws = SimpleNamespace(closed=False)
        adapter._ensure_token = AsyncMock(return_value="fictitious-platform-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            adapter._http_client = client
            return await adapter.send_private_c2c("fake-user", "private-balance-12345", "fake-event")

    with caplog.at_level(logging.DEBUG):
        result = asyncio.run(exercise())
    assert len(requests) == 1
    assert requests[0][0] == "/v2/users/fake-user/messages"
    assert requests[0][1]["content"] == "private-balance-12345"
    assert requests[0][1]["msg_id"] == "fake-event"
    assert result.success is (reply == {"id": "real-fake-platform-id"})
    if not result.success:
        assert result.retryable is False
    assert "private-balance-12345" not in caplog.text
