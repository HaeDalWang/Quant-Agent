"""브로커 값 객체 및 인터페이스 계약 테스트.

외부 의존 없이 파생 속성(평가손익·수익률)을 손계산 케이스로 검증하고,
FakeBroker로 Broker 인터페이스 계약을 확인한다.
"""

from __future__ import annotations

import pytest

from quant_agent.broker.base import Account, Broker, Position
from quant_agent.universe.models import Market, Symbol


def _pos(qty: float, avg: float, cur: float, code: str = "005930") -> Position:
    return Position(
        symbol=Symbol(code, "테스트", Market.KR),
        quantity=qty,
        avg_price=avg,
        current_price=cur,
    )


# --- Position 파생 속성 ---


def test_position_profit_case():
    """수량 10, 매입 100, 현재 120 → 수익 200, 수익률 20%."""
    p = _pos(10, 100.0, 120.0)
    assert p.cost_basis == pytest.approx(1000.0)
    assert p.market_value == pytest.approx(1200.0)
    assert p.pnl == pytest.approx(200.0)
    assert p.pnl_rate == pytest.approx(20.0)


def test_position_loss_case():
    """수량 5, 매입 200, 현재 180 → 손실 -100, 수익률 -10%."""
    p = _pos(5, 200.0, 180.0)
    assert p.pnl == pytest.approx(-100.0)
    assert p.pnl_rate == pytest.approx(-10.0)


def test_position_pnl_rate_none_when_zero_cost():
    """매입금액 0이면 수익률 None (0으로 나누기 방지)."""
    p = _pos(0, 0.0, 100.0)
    assert p.pnl_rate is None


def test_position_symbol_key_delegates():
    p = _pos(1, 100.0, 100.0, code="005930")
    assert p.symbol_key == "KR:005930"


def test_position_is_immutable():
    from dataclasses import FrozenInstanceError

    p = _pos(10, 100.0, 120.0)
    with pytest.raises(FrozenInstanceError):
        p.quantity = 20  # type: ignore[misc]


# --- Account 파생 속성 ---


def test_account_aggregates_positions():
    """현금 500 + 수익 종목 + 손실 종목."""
    account = Account(
        cash=500.0,
        positions=(
            _pos(10, 100.0, 120.0, "005930"),  # +200
            _pos(5, 200.0, 180.0, "000660"),  # -100
        ),
    )
    assert account.positions_value == pytest.approx(2100.0)  # 1200 + 900
    assert account.total_cost == pytest.approx(2000.0)  # 1000 + 1000
    assert account.total_pnl == pytest.approx(100.0)  # 200 - 100
    assert account.total_pnl_rate == pytest.approx(5.0)  # 100/2000
    assert account.total_assets == pytest.approx(2600.0)  # 500 + 2100


def test_account_empty_positions():
    """보유종목 없으면 합계 0, 수익률 None, 총자산은 현금."""
    account = Account(cash=1000.0)
    assert account.positions_value == 0
    assert account.total_cost == 0
    assert account.total_pnl == 0
    assert account.total_pnl_rate is None
    assert account.total_assets == pytest.approx(1000.0)


def test_account_is_immutable():
    from dataclasses import FrozenInstanceError

    account = Account(cash=1000.0)
    with pytest.raises(FrozenInstanceError):
        account.cash = 2000.0  # type: ignore[misc]


# --- Broker 인터페이스 계약 ---


def test_fake_broker_implements_interface():
    """구현체는 get_account()로 Account를 반환한다."""

    class FakeBroker(Broker):
        def get_account(self) -> Account:
            return Account(cash=1000.0, positions=(_pos(10, 100.0, 110.0),))

    broker = FakeBroker()
    account = broker.get_account()
    assert isinstance(account, Account)
    assert account.cash == pytest.approx(1000.0)
    assert len(account.positions) == 1
