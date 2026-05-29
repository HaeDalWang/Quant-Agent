"""규칙 엔진 — 지표 스냅샷에서 알림 가치가 있는 조건을 판단한다.

여기가 "정책"이 사는 곳이다. signals는 사실(RSI=25)을 만들고, rules는 임계값으로
그 사실이 알림할 가치가 있는지 결정한다(RSI<=30이면 과매도 신호).

설계:
- 각 규칙은 순수 함수 `IndicatorSnapshot -> Alert | None`.
- 조건 미충족 또는 데이터 부족(None)이면 None을 반환해 안전하게 건너뛴다.
- 엔진은 등록된 규칙들을 평가해 트리거된 Alert만 모은다.
- 규칙 추가 = 함수 추가 + DEFAULT_RULES 등록 (개방-폐쇄 원칙).

사유 문자열에는 실제 지표값을 담는다 — 알림 본문이자 Phase 2 LLM 컨텍스트가 된다.
"""

from __future__ import annotations

from collections.abc import Callable

from quant_agent.alerts.base import Alert, AlertLevel
from quant_agent.analysis.signals import IndicatorSnapshot

# 임계값 (매직 넘버 방지). 스윙 트레이딩 표준값에서 출발, 추후 config화 가능.
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
VOLUME_SURGE_RATIO = 2.0
# 고확신 결합 규칙용 (과매도 + 거래량) — 단일 조건보다 완화된 RSI에 거래량을 결합
COMBO_RSI_MAX = 35.0
COMBO_VOLUME_RATIO = 1.5

Rule = Callable[[IndicatorSnapshot], Alert | None]


def rule_rsi_oversold(snap: IndicatorSnapshot) -> Alert | None:
    """RSI 과매도 — 반등 매수 후보."""
    if snap.rsi is None or snap.rsi > RSI_OVERSOLD:
        return None
    return Alert(
        title="RSI 과매도",
        body=f"RSI={snap.rsi:.1f} (≤{RSI_OVERSOLD:.0f}), 종가={snap.close:,.2f}",
        level=AlertLevel.SIGNAL,
        symbol_key=snap.symbol_key,
    )


def rule_rsi_overbought(snap: IndicatorSnapshot) -> Alert | None:
    """RSI 과매수 — 차익실현·경계 신호."""
    if snap.rsi is None or snap.rsi < RSI_OVERBOUGHT:
        return None
    return Alert(
        title="RSI 과매수",
        body=f"RSI={snap.rsi:.1f} (≥{RSI_OVERBOUGHT:.0f}), 종가={snap.close:,.2f}",
        level=AlertLevel.WARNING,
        symbol_key=snap.symbol_key,
    )


def rule_macd_bullish_cross(snap: IndicatorSnapshot) -> Alert | None:
    """MACD 히스토그램 상향 교차 — 모멘텀 전환(상승)."""
    if not snap.macd_bullish_cross:
        return None
    return Alert(
        title="MACD 상향 교차",
        body=f"히스토그램 음→양 전환 (hist={snap.macd_hist:.3f}), 종가={snap.close:,.2f}",
        level=AlertLevel.SIGNAL,
        symbol_key=snap.symbol_key,
    )


def rule_macd_bearish_cross(snap: IndicatorSnapshot) -> Alert | None:
    """MACD 히스토그램 하향 교차 — 모멘텀 전환(하락)."""
    if not snap.macd_bearish_cross:
        return None
    return Alert(
        title="MACD 하향 교차",
        body=f"히스토그램 양→음 전환 (hist={snap.macd_hist:.3f}), 종가={snap.close:,.2f}",
        level=AlertLevel.WARNING,
        symbol_key=snap.symbol_key,
    )


def rule_volume_surge(snap: IndicatorSnapshot) -> Alert | None:
    """거래량 급증 — 평균 대비 이상 거래."""
    if snap.volume_ratio is None or snap.volume_ratio < VOLUME_SURGE_RATIO:
        return None
    return Alert(
        title="거래량 급증",
        body=f"거래량 {snap.volume_ratio:.1f}배 (평균 대비), 종가={snap.close:,.2f}",
        level=AlertLevel.INFO,
        symbol_key=snap.symbol_key,
    )


def rule_oversold_with_volume(snap: IndicatorSnapshot) -> Alert | None:
    """과매도 + 거래량 결합 — 고확신 반등 후보 (roadmap DoD 예시 조건)."""
    if snap.rsi is None or snap.volume_ratio is None:
        return None
    if snap.rsi > COMBO_RSI_MAX or snap.volume_ratio < COMBO_VOLUME_RATIO:
        return None
    return Alert(
        title="과매도 + 거래량 급증",
        body=(
            f"RSI={snap.rsi:.1f} (≤{COMBO_RSI_MAX:.0f}) & "
            f"거래량 {snap.volume_ratio:.1f}배, 종가={snap.close:,.2f}"
        ),
        level=AlertLevel.SIGNAL,
        symbol_key=snap.symbol_key,
    )


# 기본 규칙 집합. 평가 순서대로 알림이 쌓인다.
DEFAULT_RULES: tuple[Rule, ...] = (
    rule_oversold_with_volume,
    rule_rsi_oversold,
    rule_rsi_overbought,
    rule_macd_bullish_cross,
    rule_macd_bearish_cross,
    rule_volume_surge,
)


def evaluate(snapshot: IndicatorSnapshot, rules: tuple[Rule, ...] = DEFAULT_RULES) -> list[Alert]:
    """스냅샷에 모든 규칙을 적용해 트리거된 알림 목록을 반환한다.

    빈 리스트는 "알림할 조건 없음"을 의미한다.
    """
    alerts = []
    for rule in rules:
        alert = rule(snapshot)
        if alert is not None:
            alerts.append(alert)
    return alerts
