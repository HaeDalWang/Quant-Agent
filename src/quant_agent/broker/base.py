"""브로커(Broker) 추상 인터페이스 + 계좌 값 객체.

증권 계좌를 "어떻게" 조회하는가를 추상화한다. 첫 구현체는 한국투자증권(KIS)이며,
나중에 다른 증권사를 추가해도 이 인터페이스는 불변.

⚠️ Phase 3 범위: **읽기 전용**만 제공한다. 주문 실행(place_order)은 승인 게이트·
리스크 한도·킬 스위치가 갖춰지는 Phase 4 전까지 의도적으로 만들지 않는다.
읽기 전용 잔고조회는 실전 계좌에서도 안전하다.

설계: KIS 잔고조회 API는 한 번의 호출로 예수금 + 보유종목을 함께 반환하므로,
get_account() 하나로 Account(현금 + 포지션)를 돌려준다 — 호출·토큰 낭비를 피한다.

값 객체는 불변이며, 평가손익·수익률은 원시 값에서 파생 속성으로 계산한다
(결정론적, 저장된 값이 아니라 항상 현재 입력 기준).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from quant_agent.universe.models import Symbol


class BrokerError(Exception):
    """브로커 조회 실패 (인증·네트워크·응답 파싱 등)."""


@dataclass(frozen=True, slots=True)
class Position:
    """보유 종목 한 건 (불변).

    Attributes:
        symbol: 종목 식별 (universe.Symbol 재사용 — OHLCV 데이터와 symbol_key로 연결).
        quantity: 보유 수량.
        avg_price: 매입 평균 단가.
        current_price: 현재가.
    """

    symbol: Symbol
    quantity: float
    avg_price: float
    current_price: float

    @property
    def symbol_key(self) -> str:
        """OHLCV 저장소와 연결되는 키 (예: 'KR:005930')."""
        return self.symbol.key

    @property
    def cost_basis(self) -> float:
        """매입 금액 (수량 × 평균단가)."""
        return self.quantity * self.avg_price

    @property
    def market_value(self) -> float:
        """평가 금액 (수량 × 현재가)."""
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        """평가 손익 (평가금액 − 매입금액)."""
        return self.market_value - self.cost_basis

    @property
    def pnl_rate(self) -> float | None:
        """수익률 % (매입금액 0이면 None)."""
        if self.cost_basis == 0:
            return None
        return self.pnl / self.cost_basis * 100.0


@dataclass(frozen=True, slots=True)
class Account:
    """계좌 스냅샷 (현금 + 보유종목, 불변)."""

    cash: float  # 주문가능현금/예수금
    positions: tuple[Position, ...] = field(default_factory=tuple)

    @property
    def positions_value(self) -> float:
        """보유종목 총 평가금액."""
        return sum(p.market_value for p in self.positions)

    @property
    def total_cost(self) -> float:
        """보유종목 총 매입금액."""
        return sum(p.cost_basis for p in self.positions)

    @property
    def total_pnl(self) -> float:
        """보유종목 총 평가손익."""
        return sum(p.pnl for p in self.positions)

    @property
    def total_pnl_rate(self) -> float | None:
        """전체 수익률 % (총매입금액 0이면 None)."""
        if self.total_cost == 0:
            return None
        return self.total_pnl / self.total_cost * 100.0

    @property
    def total_assets(self) -> float:
        """총 자산 (현금 + 보유종목 평가금액)."""
        return self.cash + self.positions_value


class Broker(ABC):
    """증권 계좌 조회 인터페이스 (읽기 전용)."""

    @abstractmethod
    def get_account(self) -> Account:
        """계좌 스냅샷(현금 + 보유종목)을 조회한다.

        Raises:
            BrokerError: 인증·네트워크·응답 파싱 실패 시.
        """
        raise NotImplementedError
