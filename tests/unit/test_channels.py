"""알림 채널 테스트 — 콘솔(로그) + Discord(requests 모킹), 팩토리."""

from __future__ import annotations

import logging

import pytest

from quant_agent.alerts.base import Alert, AlertLevel
from quant_agent.alerts.console import ConsoleChannel
from quant_agent.alerts.discord import DiscordChannel
from quant_agent.alerts.factory import build_channel
from quant_agent.config.settings import Settings

# --- ConsoleChannel ---


def test_console_send_logs(caplog):
    channel = ConsoleChannel()
    with caplog.at_level(logging.INFO):
        ok = channel.send(Alert("제목", "본문", AlertLevel.SIGNAL, "US:AAPL"))
    assert ok is True
    assert "US:AAPL" in caplog.text
    assert "제목" in caplog.text


def test_console_send_report_logs(caplog):
    channel = ConsoleChannel()
    with caplog.at_level(logging.INFO):
        ok = channel.send_report("리포트", "# 내용")
    assert ok is True
    assert "리포트" in caplog.text


# --- DiscordChannel (requests 모킹) ---


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_discord_rejects_empty_url():
    with pytest.raises(ValueError, match="비어 있습니다"):
        DiscordChannel("")


def test_discord_send_success(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(204)

    monkeypatch.setattr("quant_agent.alerts.discord.requests.post", fake_post)
    channel = DiscordChannel("https://discord.com/api/webhooks/x")

    ok = channel.send(Alert("제목", "본문", AlertLevel.SIGNAL, "US:AAPL"))

    assert ok is True
    assert captured["url"] == "https://discord.com/api/webhooks/x"
    assert "embeds" in captured["json"]
    assert "US:AAPL" in captured["json"]["embeds"][0]["title"]


def test_discord_send_http_error_returns_false(monkeypatch):
    monkeypatch.setattr(
        "quant_agent.alerts.discord.requests.post",
        lambda *a, **k: _FakeResponse(429, "rate limited"),
    )
    channel = DiscordChannel("https://discord.com/api/webhooks/x")
    assert channel.send(Alert("제목", "본문")) is False


def test_discord_network_error_returns_false(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.RequestException("연결 실패")

    monkeypatch.setattr("quant_agent.alerts.discord.requests.post", boom)
    channel = DiscordChannel("https://discord.com/api/webhooks/x")
    # 예외가 아니라 False (장애 격리)
    assert channel.send(Alert("제목", "본문")) is False


def test_discord_report_truncates(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResponse(204)

    monkeypatch.setattr("quant_agent.alerts.discord.requests.post", fake_post)
    channel = DiscordChannel("https://discord.com/api/webhooks/x")

    huge = "x" * 5000
    channel.send_report("리포트", huge)

    # Discord content 제한(2000) 이하로 잘렸는지
    assert len(captured["json"]["content"]) <= 2000


# --- factory ---


def test_factory_returns_console_without_url():
    settings = Settings(_env_file=None)
    assert isinstance(build_channel(settings), ConsoleChannel)


def test_factory_returns_discord_with_url():
    settings = Settings(_env_file=None, discord_webhook_url="https://discord.com/x")
    assert isinstance(build_channel(settings), DiscordChannel)
