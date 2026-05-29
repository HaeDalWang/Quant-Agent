"""테스트 공용 fixture 및 fake 구현.

외부 네트워크/IO 없이 단위 테스트가 가능하도록 Collector/Store의 인메모리
fake를 제공한다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_agent.collectors.base import (
    OHLCV_COLUMNS,
    Collector,
    CollectorError,
    empty_ohlcv,
)
from quant_agent.universe.models import Market, Symbol


def make_ohlcv(symbol_key: str, days: list[date]) -> pd.DataFrame:
    """주어진 날짜들로 OHLCV 표준 스키마 DataFrame을 만든다."""
    rows = [
        {
            "symbol_key": symbol_key,
            "dt": d,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000 + i,
        }
        for i, d in enumerate(days)
    ]
    return pd.DataFrame(rows, columns=list(OHLCV_COLUMNS))


class FakeCollector(Collector):
    """미리 지정한 데이터를 반환하거나, 지정 종목에서 실패를 시뮬레이션한다."""

    def __init__(
        self,
        data: dict[str, pd.DataFrame] | None = None,
        fail_keys: set[str] | None = None,
        supported: set[Market] | None = None,
    ) -> None:
        self._data = data or {}
        self._fail_keys = fail_keys or set()
        self._supported = supported or {Market.KR, Market.US}

    def supports(self, market: Market) -> bool:
        return market in self._supported

    def fetch(self, symbol: Symbol, start: date, end: date) -> pd.DataFrame:
        if symbol.key in self._fail_keys:
            raise CollectorError(f"의도된 실패: {symbol.key}")
        return self._data.get(symbol.key, empty_ohlcv())


@pytest.fixture
def kr_symbol() -> Symbol:
    return Symbol("005930", "삼성전자", Market.KR)


@pytest.fixture
def us_symbol() -> Symbol:
    return Symbol("AAPL", "Apple", Market.US)
