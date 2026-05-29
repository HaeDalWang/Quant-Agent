"""유니버스 모델·티어 및 시장 감지 테스트."""

from __future__ import annotations

import pytest

from quant_agent.collectors.price import FinanceDataReaderCollector
from quant_agent.universe.models import Market, Symbol
from quant_agent.universe.tiers import TIER1_CORE, tier1_symbols


def test_symbol_key_format():
    s = Symbol("005930", "삼성전자", Market.KR)
    assert s.key == "KR:005930"


def test_symbol_rejects_empty_code():
    with pytest.raises(ValueError, match="비어 있을 수 없습니다"):
        Symbol("", "이름", Market.KR)


def test_symbol_is_immutable():
    """frozen dataclass는 변경 불가."""
    from dataclasses import FrozenInstanceError

    s = Symbol("AAPL", "Apple", Market.US)
    with pytest.raises(FrozenInstanceError):
        s.code = "MSFT"  # type: ignore[misc]


def test_tier1_has_both_markets():
    markets = {s.market for s in TIER1_CORE}
    assert markets == {Market.KR, Market.US}


def test_tier1_filter_by_market():
    kr = tier1_symbols(Market.KR)
    us = tier1_symbols(Market.US)
    assert all(s.market is Market.KR for s in kr)
    assert all(s.market is Market.US for s in us)
    assert len(kr) + len(us) == len(TIER1_CORE)


def test_tier1_keys_are_unique():
    keys = [s.key for s in TIER1_CORE]
    assert len(keys) == len(set(keys))


def test_collector_market_detection():
    """FDR 수집기는 KR·US를 지원한다."""
    collector = FinanceDataReaderCollector()
    assert collector.supports(Market.KR) is True
    assert collector.supports(Market.US) is True
