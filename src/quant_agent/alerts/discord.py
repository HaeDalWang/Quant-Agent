"""Discord webhook 알림 채널.

Discord webhook으로 알림·리포트를 전송한다. 알림은 embed(색상으로 중요도 구분),
리포트는 코드블록 형태로 보낸다.

네트워크 실패는 예외를 던지지 않고 False를 반환한다 — 한 알림의 실패가 전체 배치를
멈추지 않도록(장애 격리). 실패 상세는 로그로 남긴다.

채널 선택 근거(승인 버튼·멀티에이전트 페르소나·검색 히스토리)는
docs/architecture.md 참고. Phase 4에서 버튼 승인 게이트로 확장된다.
"""

from __future__ import annotations

import logging

import requests

from quant_agent.alerts.base import Alert, AlertChannel, AlertLevel

logger = logging.getLogger(__name__)

# Discord 제약
_CONTENT_LIMIT = 2000
_EMBED_DESC_LIMIT = 4096
_REQUEST_TIMEOUT = 10  # 초

# 중요도 → embed 색상 (10진 RGB)
_LEVEL_COLOR = {
    AlertLevel.INFO: 0x3498DB,  # 파랑
    AlertLevel.SIGNAL: 0x2ECC71,  # 초록
    AlertLevel.WARNING: 0xE74C3C,  # 빨강
}


def _truncate(text: str, limit: int) -> str:
    """길이 제한을 초과하면 말줄임표로 자른다."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class DiscordChannel(AlertChannel):
    """Discord webhook 채널."""

    def __init__(self, webhook_url: str, timeout: int = _REQUEST_TIMEOUT) -> None:
        if not webhook_url or not webhook_url.strip():
            raise ValueError("Discord webhook URL이 비어 있습니다.")
        self._webhook_url = webhook_url
        self._timeout = timeout

    def send(self, alert: Alert) -> bool:
        title = f"[{alert.symbol_key}] {alert.title}" if alert.symbol_key else alert.title
        payload = {
            "embeds": [
                {
                    "title": _truncate(title, 256),
                    "description": _truncate(alert.body, _EMBED_DESC_LIMIT),
                    "color": _LEVEL_COLOR.get(alert.level, _LEVEL_COLOR[AlertLevel.INFO]),
                }
            ]
        }
        return self._post(payload, context=f"alert:{alert.symbol_key or alert.title}")

    def send_report(self, title: str, markdown: str) -> bool:
        # 리포트는 content에 코드블록으로. 래퍼 길이에서 예산을 직접 계산해 제한을 지킨다.
        prefix = f"**{title}**\n```md\n"
        suffix = "\n```"
        budget = _CONTENT_LIMIT - len(prefix) - len(suffix)
        body = _truncate(markdown, budget)
        content = f"{prefix}{body}{suffix}"
        return self._post({"content": content}, context=f"report:{title}")

    def _post(self, payload: dict, context: str) -> bool:
        """webhook으로 payload를 전송한다. 실패 시 False."""
        try:
            resp = requests.post(self._webhook_url, json=payload, timeout=self._timeout)
            if resp.status_code >= 400:
                logger.warning(
                    "Discord 전송 실패 (%s): HTTP %d %s",
                    context,
                    resp.status_code,
                    resp.text[:200],
                )
                return False
            return True
        except requests.RequestException as exc:
            logger.warning("Discord 전송 오류 (%s): %s", context, exc)
            return False
