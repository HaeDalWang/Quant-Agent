"""규칙 엔진 테스트 — 임계값 경계와 알림 생성."""

from __future__ import annotations

from datetime import date

from quant_agent.alerts.base import AlertLevel
from quant_agent.alerts.rules import (
    COMBO_RSI_MAX,
    COMBO_VOLUME_RATIO,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    VOLUME_SURGE_RATIO,
    evaluate,
    rule_macd_bearish_cross,
    rule_macd_bullish_cross,
    rule_oversold_with_volume,
    rule_rsi_overbought,
    rule_rsi_oversold,
    rule_volume_surge,
)
from quant_agent.analysis.signals import IndicatorSnapshot


def _snap(**overrides) -> IndicatorSnapshot:
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


# --- RSI 과매도 ---


def test_rsi_oversold_triggers_below_threshold():
    alert = rule_rsi_oversold(_snap(rsi=RSI_OVERSOLD - 5))
    assert alert is not None
    assert alert.level is AlertLevel.SIGNAL
    assert alert.symbol_key == "US:TEST"


def test_rsi_oversold_silent_above_threshold():
    assert rule_rsi_oversold(_snap(rsi=RSI_OVERSOLD + 5)) is None


def test_rsi_oversold_silent_when_none():
    assert rule_rsi_oversold(_snap(rsi=None)) is None


# --- RSI 과매수 ---


def test_rsi_overbought_triggers():
    alert = rule_rsi_overbought(_snap(rsi=RSI_OVERBOUGHT + 5))
    assert alert is not None
    assert alert.level is AlertLevel.WARNING


def test_rsi_overbought_silent_below():
    assert rule_rsi_overbought(_snap(rsi=RSI_OVERBOUGHT - 5)) is None


# --- MACD 교차 ---


def test_macd_bullish_cross_rule():
    alert = rule_macd_bullish_cross(_snap(macd_hist=0.5, macd_hist_prev=-0.2))
    assert alert is not None
    assert alert.level is AlertLevel.SIGNAL


def test_macd_bearish_cross_rule():
    alert = rule_macd_bearish_cross(_snap(macd_hist=-0.5, macd_hist_prev=0.2))
    assert alert is not None
    assert alert.level is AlertLevel.WARNING


# --- 거래량 급증 ---


def test_volume_surge_triggers():
    alert = rule_volume_surge(_snap(volume_ratio=VOLUME_SURGE_RATIO + 0.5))
    assert alert is not None


def test_volume_surge_silent_below():
    assert rule_volume_surge(_snap(volume_ratio=VOLUME_SURGE_RATIO - 0.5)) is None


# --- 결합 규칙 ---


def test_combo_rule_triggers_when_both_met():
    alert = rule_oversold_with_volume(
        _snap(rsi=COMBO_RSI_MAX - 2, volume_ratio=COMBO_VOLUME_RATIO + 0.5)
    )
    assert alert is not None
    assert alert.level is AlertLevel.SIGNAL


def test_combo_rule_silent_when_only_one_met():
    # RSI는 충족하나 거래량 미달
    assert (
        rule_oversold_with_volume(
            _snap(rsi=COMBO_RSI_MAX - 2, volume_ratio=COMBO_VOLUME_RATIO - 0.5)
        )
        is None
    )


# --- evaluate 통합 ---


def test_evaluate_collects_multiple_alerts():
    """과매도 + 거래량 급증이면 여러 규칙이 동시 트리거된다."""
    snap = _snap(rsi=25.0, volume_ratio=3.0)
    alerts = evaluate(snap)
    titles = {a.title for a in alerts}
    # 결합 규칙 + 단일 과매도 + 거래량 급증
    assert "과매도 + 거래량 급증" in titles
    assert "RSI 과매도" in titles
    assert "거래량 급증" in titles


def test_evaluate_empty_when_neutral():
    """중립 스냅샷은 알림 없음."""
    snap = _snap(rsi=50.0, volume_ratio=1.0, macd_hist=0.1, macd_hist_prev=0.1)
    assert evaluate(snap) == []
