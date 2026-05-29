"""기술적 지표 계산 — 순수 함수, 결정론적.

모든 함수는 입력 Series를 변경하지 않고 새 Series를 반환한다(불변성).
지표 계산은 AI 경계 아래에 있으므로, 같은 입력이면 항상 같은 출력이어야 한다.

RSI와 ATR은 Wilder 평활(alpha = 1/period)을 사용한다. 이는 대부분의 차팅
플랫폼(TradingView 기본값 등)이 쓰는 표준 방식이며, pandas의
`.ewm(alpha=1/period, adjust=False)`로 정확히 표현된다.

지표는 OHLCV DataFrame이 아니라 개별 Series를 받는다 — 단위 테스트와 재사용을
쉽게 하기 위함이다. DataFrame과의 연결은 상위 레이어(signals)가 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 기본 파라미터 (매직 넘버 방지)
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14


@dataclass(frozen=True, slots=True)
class MACDResult:
    """MACD 계산 결과 (불변).

    Attributes:
        line: MACD 라인 (빠른 EMA - 느린 EMA).
        signal: 시그널 라인 (MACD 라인의 EMA).
        histogram: line - signal.
    """

    line: pd.Series
    signal: pd.Series
    histogram: pd.Series


def sma(series: pd.Series, period: int) -> pd.Series:
    """단순 이동평균 (Simple Moving Average)."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """지수 이동평균 (Exponential Moving Average).

    adjust=False로 재귀적(recursive) 형태를 사용해 차팅 플랫폼과 일치시킨다.
    """
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """상대강도지수 (RSI), Wilder 평활.

    범위는 [0, 100]. 하락이 전혀 없으면(avg_loss=0) RSI=100으로 정의한다.

    Args:
        close: 종가 Series.
        period: 평활 기간 (기본 14).

    Returns:
        RSI Series (입력과 동일 인덱스, 초기 구간은 워밍업 값).
    """
    delta = close.diff()
    # 첫 행의 NaN은 where 조건이 False가 되어 0.0으로 처리된다.
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    result = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss=0 → rs=inf → result=100. avg_gain=avg_loss=0 → 0/0=NaN → 50으로 정의.
    result = result.where(avg_loss != 0, 100.0)
    result = result.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return result


def macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> MACDResult:
    """MACD (Moving Average Convergence Divergence).

    line = EMA(fast) - EMA(slow), signal = EMA(line, signal), hist = line - signal.
    """
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    line = fast_ema - slow_ema
    signal_line = ema(line, signal)
    histogram = line - signal_line
    return MACDResult(line=line, signal=signal_line, histogram=histogram)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range (TR).

    TR = max(high-low, |high-prev_close|, |low-prev_close|).
    """
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ATR_PERIOD,
) -> pd.Series:
    """Average True Range (ATR), Wilder 평활."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
