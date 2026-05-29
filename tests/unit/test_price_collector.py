"""FinanceDataReader 수집기 테스트 — 정규화 로직 (네트워크 없이 모킹)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_agent.collectors.base import OHLCV_COLUMNS, CollectorError
from quant_agent.collectors.price import FinanceDataReaderCollector
from quant_agent.universe.models import Market, Symbol


def _fdr_like_frame() -> pd.DataFrame:
    """FinanceDataReader 반환 형식 모사: DatetimeIndex + Open/High/Low/Close/Volume."""
    idx = pd.DatetimeIndex([date(2026, 5, 1), date(2026, 5, 2)], name="Date")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 2000],
        },
        index=idx,
    )


def test_normalize_to_standard_schema(monkeypatch):
    """FDR 원본을 표준 OHLCV 스키마로 정규화한다."""
    # Arrange
    monkeypatch.setattr(
        "quant_agent.collectors.price.fdr.DataReader",
        lambda *a, **k: _fdr_like_frame(),
    )
    collector = FinanceDataReaderCollector()
    symbol = Symbol("005930", "삼성전자", Market.KR)

    # Act
    df = collector.fetch(symbol, date(2026, 5, 1), date(2026, 5, 2))

    # Assert
    assert list(df.columns) == list(OHLCV_COLUMNS)
    assert len(df) == 2
    assert (df["symbol_key"] == "KR:005930").all()
    assert df.iloc[0]["dt"] == date(2026, 5, 1)
    assert df.iloc[0]["close"] == 101.0


def test_empty_result_returns_empty_schema(monkeypatch):
    monkeypatch.setattr(
        "quant_agent.collectors.price.fdr.DataReader",
        lambda *a, **k: pd.DataFrame(),
    )
    collector = FinanceDataReaderCollector()
    symbol = Symbol("AAPL", "Apple", Market.US)

    df = collector.fetch(symbol, date(2026, 5, 1), date(2026, 5, 2))

    assert df.empty
    assert list(df.columns) == list(OHLCV_COLUMNS)


def test_fetch_wraps_source_error(monkeypatch):
    """소스 예외를 도메인 예외(CollectorError)로 변환한다."""

    def _boom(*a, **k):
        raise ValueError("네트워크 오류")

    monkeypatch.setattr("quant_agent.collectors.price.fdr.DataReader", _boom)
    collector = FinanceDataReaderCollector()
    symbol = Symbol("005930", "삼성전자", Market.KR)

    with pytest.raises(CollectorError, match="시세 수집 실패"):
        collector.fetch(symbol, date(2026, 5, 1), date(2026, 5, 2))


def test_does_not_mutate_input(monkeypatch):
    """정규화는 입력 DataFrame을 변경하지 않는다 (불변성)."""
    original = _fdr_like_frame()
    snapshot = original.copy(deep=True)
    monkeypatch.setattr(
        "quant_agent.collectors.price.fdr.DataReader",
        lambda *a, **k: original,
    )
    collector = FinanceDataReaderCollector()

    collector.fetch(Symbol("005930", "삼성전자", Market.KR), date(2026, 5, 1), date(2026, 5, 2))

    # 원본 컬럼·인덱스가 그대로인지 확인
    pd.testing.assert_frame_equal(original, snapshot)
