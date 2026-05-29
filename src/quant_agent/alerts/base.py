"""알림 채널 추상 인터페이스 + 알림 값 객체.

사람에게 "어떻게" 전달하는가를 추상화한다. 채널(Console, Discord, 추후 Telegram)이
바뀌어도 상위 레이어(rules, service)는 영향받지 않는다.

Alert는 구조화된 값 객체다 — 채널마다 동일한 데이터를 각자의 방식으로 렌더링한다
(콘솔은 평문, Discord는 embed). 이 분리 덕분에 규칙 레이어는 표현 형식을 모른다.

Phase 4에서 request_approval(proposal) -> decision (Discord 버튼 승인 게이트)을
추가할 예정이지만, 지금 만들지 않는다(YAGNI).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class AlertLevel(StrEnum):
    """알림 중요도."""

    INFO = "INFO"
    SIGNAL = "SIGNAL"  # 매매 신호 후보
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class Alert:
    """단일 알림 (불변, 표현 형식 무관).

    Attributes:
        title: 한 줄 제목.
        body: 본문 (사유·지표값 등).
        level: 중요도.
        symbol_key: 관련 종목 키 (없으면 None).
    """

    title: str
    body: str
    level: AlertLevel = AlertLevel.INFO
    symbol_key: str | None = None


class AlertError(Exception):
    """알림 전송 실패."""


class AlertChannel(ABC):
    """알림 채널 인터페이스."""

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """단일 알림을 전송한다.

        Returns:
            전송 성공 여부. 실패는 로그로 남기되, 한 알림의 실패가 배치를
            멈추지 않도록 False 반환을 허용한다(예외 대신).
        """
        raise NotImplementedError

    @abstractmethod
    def send_report(self, title: str, markdown: str) -> bool:
        """정기 리포트(마크다운)를 전송한다."""
        raise NotImplementedError
