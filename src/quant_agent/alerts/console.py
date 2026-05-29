"""콘솔 알림 채널 — 네트워크 없이 stdout/로그로 출력.

기본 채널이자 테스트용. webhook URL이 설정되지 않은 환경(개발·CI)에서 안전하게
동작하며, 규칙·리포트 로직을 네트워크 의존 없이 검증할 수 있게 한다.
"""

from __future__ import annotations

import logging

from quant_agent.alerts.base import Alert, AlertChannel

logger = logging.getLogger(__name__)


class ConsoleChannel(AlertChannel):
    """알림을 로그로 출력하는 채널."""

    def send(self, alert: Alert) -> bool:
        prefix = f"[{alert.level}]"
        if alert.symbol_key:
            prefix += f" {alert.symbol_key}"
        logger.info("%s %s — %s", prefix, alert.title, alert.body)
        return True

    def send_report(self, title: str, markdown: str) -> bool:
        logger.info("[REPORT] %s\n%s", title, markdown)
        return True
