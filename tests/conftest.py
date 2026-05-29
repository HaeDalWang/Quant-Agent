"""테스트 공용 fixture 및 fake 구현.

외부 네트워크/IO 없이 단위 테스트가 가능하도록 Collector/Store의 인메모리
fake를 제공한다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from quant_agent.collectors.base import (
    OHLCV_COLUMNS,
    Collector,
    CollectorError,
    empty_ohlcv,
)
from quant_agent.universe.models import Market, Symbol


@pytest.fixture(autouse=True)
def _block_external_services(monkeypatch):
    """모든 테스트에서 실제 외부 서비스 시크릿을 차단한다 (안전 가드).

    테스트가 실수로 진짜 Discord webhook이나 DART API로 나가는 것을 원천 차단한다.

    주의: pydantic-settings는 환경변수가 없으면 .env 파일을 읽으므로, delenv로는
    부족하다(.env의 실제 URL로 폴백됨). 환경변수를 빈 문자열로 강제 설정해 .env
    값을 덮어써야 한다 — 그러면 채널 팩토리가 ConsoleChannel로 폴백한다.
    """
    monkeypatch.setenv("QA_DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("QA_DART_API_KEY", "")


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


def make_ohlcv_series(
    symbol_key: str,
    closes: list[float],
    *,
    start: date = date(2026, 1, 1),
    volumes: list[float] | None = None,
    high_offset: float = 1.0,
    low_offset: float = 1.0,
) -> pd.DataFrame:
    """종가 리스트로 N개 봉의 OHLCV를 만든다 (지표 테스트용).

    high = close + high_offset, low = close - low_offset로 단순 구성한다.
    """
    n = len(closes)
    vols = volumes if volumes is not None else [1000.0] * n
    rows = [
        {
            "symbol_key": symbol_key,
            "dt": start + timedelta(days=i),
            "open": closes[i],
            "high": closes[i] + high_offset,
            "low": closes[i] - low_offset,
            "close": closes[i],
            "volume": vols[i],
        }
        for i in range(n)
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
