"""지표 스냅샷 — OHLCV에서 최신 봉의 구조화된 지표 관측값을 추출한다.

`signals`는 "사실"을 만든다: RSI=25.3, ATR%=3.1, MACD 히스토그램 부호 등.
이 사실들을 어떻게 조합해 알림할지(임계값·정책)는 `alerts/rules.py`가 결정한다.

교차(crossover)는 두 원시값에서 나오는 결정론적 구조 사실이므로 스냅샷 속성으로
제공한다. 반면 "RSI<30이면 과매도" 같은 임계값 판단은 정책이라 규칙 레이어로 분리한다.

이 스냅샷은 알림·리포트의 입력이자, Phase 2에서 LLM이 읽는 구조화 컨텍스트가 된다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant_agent.analysis import indicators as ind

# 스윙 트레이딩 표준 이동평균 기간
SMA_SHORT = 20
SMA_LONG = 50
VOLUME_AVG_WINDOW = 20

# 스냅샷 계산에 필요한 최소 봉 수 (가장 긴 지표 + 여유)
MIN_BARS = SMA_LONG


def _scalar(value: float) -> float | None:
    """pandas 스칼라를 float | None으로 정규화한다 (NaN → None)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    """최신 봉의 지표 스냅샷 (불변, 원시 관측값)."""

    symbol_key: str
    dt: date
    close: float

    sma_short: float | None
    sma_long: float | None
    rsi: float | None

    macd_line: float | None
    macd_signal: float | None
    macd_hist: float | None
    macd_hist_prev: float | None

    atr: float | None
    atr_pct: float | None  # ATR / close * 100 (변동성 스윗스팟 판정용)

    volume: float
    avg_volume: float | None
    volume_ratio: float | None  # volume / avg_volume (거래량 급증 판정용)

    # --- 구조적 파생 사실 (임계값 아닌 부호/교차) ---

    @property
    def macd_bullish_cross(self) -> bool:
        """MACD 히스토그램이 음→양으로 전환 (상향 교차)."""
        if self.macd_hist is None or self.macd_hist_prev is None:
            return False
        return self.macd_hist_prev <= 0 < self.macd_hist

    @property
    def macd_bearish_cross(self) -> bool:
        """MACD 히스토그램이 양→음으로 전환 (하향 교차)."""
        if self.macd_hist is None or self.macd_hist_prev is None:
            return False
        return self.macd_hist_prev >= 0 > self.macd_hist

    @property
    def price_above_short_ma(self) -> bool | None:
        if self.sma_short is None:
            return None
        return self.close > self.sma_short


def compute_snapshot(df: pd.DataFrame, symbol_key: str) -> IndicatorSnapshot | None:
    """OHLCV DataFrame에서 최신 봉의 지표 스냅샷을 계산한다.

    Args:
        df: OHLCV 표준 스키마. dt 오름차순 정렬을 가정하지 않고 내부에서 정렬한다.
        symbol_key: 종목 키.

    Returns:
        최신 봉 스냅샷. 데이터가 MIN_BARS 미만이면 None.
    """
    if df is None or df.empty:
        return None

    data = df.sort_values("dt").reset_index(drop=True)
    if len(data) < MIN_BARS:
        return None

    close = data["close"]
    macd = ind.macd(close)
    rsi_series = ind.rsi(close)
    sma_s = ind.sma(close, SMA_SHORT)
    sma_l = ind.sma(close, SMA_LONG)
    atr_series = ind.atr(data["high"], data["low"], close)
    vol_avg = data["volume"].rolling(VOLUME_AVG_WINDOW, min_periods=VOLUME_AVG_WINDOW).mean()

    last = len(data) - 1
    close_val = float(close.iloc[last])

    atr_val = _scalar(atr_series.iloc[last])
    atr_pct = (atr_val / close_val * 100.0) if (atr_val is not None and close_val) else None

    volume_val = float(data["volume"].iloc[last])
    avg_vol = _scalar(vol_avg.iloc[last])
    vol_ratio = (volume_val / avg_vol) if (avg_vol is not None and avg_vol > 0) else None

    macd_hist_prev = _scalar(macd.histogram.iloc[last - 1]) if last >= 1 else None

    return IndicatorSnapshot(
        symbol_key=symbol_key,
        dt=data["dt"].iloc[last],
        close=close_val,
        sma_short=_scalar(sma_s.iloc[last]),
        sma_long=_scalar(sma_l.iloc[last]),
        rsi=_scalar(rsi_series.iloc[last]),
        macd_line=_scalar(macd.line.iloc[last]),
        macd_signal=_scalar(macd.signal.iloc[last]),
        macd_hist=_scalar(macd.histogram.iloc[last]),
        macd_hist_prev=macd_hist_prev,
        atr=atr_val,
        atr_pct=atr_pct,
        volume=volume_val,
        avg_volume=avg_vol,
        volume_ratio=vol_ratio,
    )
