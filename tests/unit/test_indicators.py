"""기술적 지표 테스트.

자기 출력을 기대값으로 박는 순환 테스트 대신, 수학적으로 반드시 성립하는
속성과 손계산 가능한 케이스로 검증한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_agent.analysis import indicators as ind


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype="float64")


# --- SMA ---


def test_sma_hand_computed():
    s = _series([1, 2, 3, 4, 5])
    result = ind.sma(s, 3)
    # 처음 2개는 NaN(min_periods=3), 이후 이동평균
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)  # (1+2+3)/3
    assert result.iloc[3] == pytest.approx(3.0)  # (2+3+4)/3
    assert result.iloc[4] == pytest.approx(4.0)  # (3+4+5)/3


# --- EMA ---


def test_ema_of_constant_is_constant():
    """상수 시리즈의 EMA는 그 상수와 같다."""
    s = _series([5.0] * 10)
    result = ind.ema(s, 3)
    assert result.iloc[-1] == pytest.approx(5.0)


def test_ema_first_value_equals_input():
    """adjust=False EMA의 첫 값은 입력 첫 값과 같다."""
    s = _series([10.0, 20.0, 30.0])
    result = ind.ema(s, 5)
    assert result.iloc[0] == pytest.approx(10.0)


def test_ema_recursive_formula():
    """EMA[i] = alpha*x[i] + (1-alpha)*EMA[i-1], span=2 → alpha=2/3."""
    s = _series([10.0, 20.0])
    result = ind.ema(s, 2)
    alpha = 2 / (2 + 1)
    expected = alpha * 20.0 + (1 - alpha) * 10.0
    assert result.iloc[1] == pytest.approx(expected)


# --- RSI ---


def test_rsi_all_gains_is_100():
    """단조 증가 시 손실이 없어 RSI=100."""
    s = _series([float(i) for i in range(1, 30)])
    result = ind.rsi(s, 14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    """단조 감소 시 이득이 없어 RSI=0."""
    s = _series([float(i) for i in range(30, 1, -1)])
    result = ind.rsi(s, 14)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_rsi_constant_is_50():
    """변동이 없으면(이득=손실=0) RSI=50으로 정의."""
    s = _series([100.0] * 20)
    result = ind.rsi(s, 14)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_rsi_within_bounds():
    """RSI는 항상 [0, 100] 범위."""
    rng = np.random.default_rng(42)
    s = _series(list(100 + rng.standard_normal(100).cumsum()))
    result = ind.rsi(s, 14).dropna()
    assert (result >= 0).all()
    assert (result <= 100).all()


# --- MACD ---


def test_macd_structure():
    """histogram = line - signal 항등식."""
    rng = np.random.default_rng(1)
    s = _series(list(100 + rng.standard_normal(60).cumsum()))
    result = ind.macd(s)
    diff = (result.histogram - (result.line - result.signal)).abs()
    assert diff.max() == pytest.approx(0.0, abs=1e-9)


def test_macd_constant_series_is_zero():
    """상수 시리즈는 두 EMA가 같아 MACD 라인=0."""
    s = _series([50.0] * 50)
    result = ind.macd(s)
    assert result.line.iloc[-1] == pytest.approx(0.0)
    assert result.histogram.iloc[-1] == pytest.approx(0.0)


# --- ATR / True Range ---


def test_true_range_first_bar_is_high_low():
    """첫 봉은 이전 종가가 없어 TR=high-low."""
    high = _series([10.0, 12.0])
    low = _series([8.0, 9.0])
    close = _series([9.0, 11.0])
    tr = ind.true_range(high, low, close)
    assert tr.iloc[0] == pytest.approx(2.0)  # 10-8


def test_true_range_uses_prev_close_gap():
    """갭 상승 시 TR은 high - prev_close를 반영."""
    # 2번째 봉: high=20, low=18, prev_close=10 → max(2, 10, 8)=10
    high = _series([12.0, 20.0])
    low = _series([8.0, 18.0])
    close = _series([10.0, 19.0])
    tr = ind.true_range(high, low, close)
    assert tr.iloc[1] == pytest.approx(10.0)


def test_atr_is_non_negative():
    rng = np.random.default_rng(7)
    base = 100 + rng.standard_normal(50).cumsum()
    high = _series(list(base + 2))
    low = _series(list(base - 2))
    close = _series(list(base))
    result = ind.atr(high, low, close, 14).dropna()
    assert (result >= 0).all()


# --- 불변성 ---


def test_indicators_do_not_mutate_input():
    s = _series([1.0, 2.0, 3.0, 4.0, 5.0])
    snapshot = s.copy()
    ind.sma(s, 3)
    ind.ema(s, 3)
    ind.rsi(s, 3)
    ind.macd(s)
    pd.testing.assert_series_equal(s, snapshot)
