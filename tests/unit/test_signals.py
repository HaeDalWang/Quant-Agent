"""지표 스냅샷 테스트."""

from __future__ import annotations

from datetime import date

from quant_agent.analysis.signals import (
    MIN_BARS,
    IndicatorSnapshot,
    compute_snapshot,
)
from tests.conftest import make_ohlcv_series


def _snap(**overrides) -> IndicatorSnapshot:
    """교차 속성 테스트용 최소 스냅샷 빌더."""
    base = dict(
        symbol_key="US:TEST",
        dt=date(2026, 5, 1),
        close=100.0,
        sma_short=None,
        sma_long=None,
        rsi=None,
        macd_line=None,
        macd_signal=None,
        macd_hist=None,
        macd_hist_prev=None,
        atr=None,
        atr_pct=None,
        volume=1000.0,
        avg_volume=None,
        volume_ratio=None,
    )
    base.update(overrides)
    return IndicatorSnapshot(**base)


# --- compute_snapshot 데이터 흐름 ---


def test_returns_none_when_insufficient_bars():
    df = make_ohlcv_series("US:TEST", [100.0] * (MIN_BARS - 1))
    assert compute_snapshot(df, "US:TEST") is None


def test_returns_none_for_empty():
    import pandas as pd

    assert compute_snapshot(pd.DataFrame(), "US:TEST") is None


def test_snapshot_latest_close():
    closes = [float(100 + i) for i in range(MIN_BARS + 5)]
    df = make_ohlcv_series("US:TEST", closes)
    snap = compute_snapshot(df, "US:TEST")
    assert snap is not None
    assert snap.close == closes[-1]
    assert snap.symbol_key == "US:TEST"


def test_snapshot_sorts_unordered_input():
    """입력이 역순이어도 최신 봉을 올바르게 잡는다."""
    closes = [float(100 + i) for i in range(MIN_BARS + 5)]
    df = make_ohlcv_series("US:TEST", closes)
    shuffled = df.iloc[::-1].reset_index(drop=True)  # 역순
    snap = compute_snapshot(shuffled, "US:TEST")
    assert snap is not None
    assert snap.close == closes[-1]  # 날짜 기준 최신


def test_volume_ratio_detects_surge():
    """마지막 봉 거래량 급증이 volume_ratio에 반영된다."""
    n = MIN_BARS + 5
    closes = [100.0] * n
    volumes = [1000.0] * n
    volumes[-1] = 3000.0  # 마지막 봉 3배
    df = make_ohlcv_series("US:TEST", closes, volumes=volumes)
    snap = compute_snapshot(df, "US:TEST")
    assert snap is not None
    assert snap.volume_ratio is not None
    assert snap.volume_ratio > 2.0


def test_atr_pct_is_positive():
    closes = [float(100 + (i % 5)) for i in range(MIN_BARS + 5)]
    df = make_ohlcv_series("US:TEST", closes, high_offset=2.0, low_offset=2.0)
    snap = compute_snapshot(df, "US:TEST")
    assert snap is not None
    assert snap.atr_pct is not None
    assert snap.atr_pct > 0


# --- 교차 속성 (직접 구성, 결정론적) ---


def test_macd_bullish_cross_true():
    snap = _snap(macd_hist=0.5, macd_hist_prev=-0.3)
    assert snap.macd_bullish_cross is True
    assert snap.macd_bearish_cross is False


def test_macd_bearish_cross_true():
    snap = _snap(macd_hist=-0.5, macd_hist_prev=0.3)
    assert snap.macd_bearish_cross is True
    assert snap.macd_bullish_cross is False


def test_macd_cross_false_when_same_sign():
    snap = _snap(macd_hist=0.5, macd_hist_prev=0.3)
    assert snap.macd_bullish_cross is False
    assert snap.macd_bearish_cross is False


def test_macd_cross_false_when_none():
    snap = _snap(macd_hist=None, macd_hist_prev=None)
    assert snap.macd_bullish_cross is False
    assert snap.macd_bearish_cross is False


def test_price_above_short_ma():
    assert _snap(close=110.0, sma_short=100.0).price_above_short_ma is True
    assert _snap(close=90.0, sma_short=100.0).price_above_short_ma is False
    assert _snap(close=110.0, sma_short=None).price_above_short_ma is None
