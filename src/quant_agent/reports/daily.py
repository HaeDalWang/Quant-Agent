"""정기 리포트 생성 — 스냅샷·알림을 마크다운으로 렌더링한다.

순수 함수다: (날짜, 스냅샷+알림 목록) → 마크다운 문자열. IO가 없어 테스트가 쉽고,
전송은 service 레이어가 AlertChannel.send_report로 처리한다.

리포트 구성:
1. 헤더 (날짜, 분석 종목 수, 트리거된 알림 수)
2. 알림 섹션 (오늘 트리거된 신호 — 가장 실행 가능한 부분)
3. 스냅샷 테이블 (종목별 핵심 지표 — 전체 시장 조망)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from quant_agent.alerts.base import Alert
from quant_agent.analysis.signals import IndicatorSnapshot


@dataclass(frozen=True, slots=True)
class SymbolAnalysis:
    """한 종목의 분석 결과 (스냅샷 + 트리거된 알림). 불변."""

    snapshot: IndicatorSnapshot
    alerts: tuple[Alert, ...]


def _fmt(value: float | None, spec: str = ".1f") -> str:
    """None은 '-', 숫자는 포맷 적용."""
    if value is None:
        return "-"
    return format(value, spec)


def _alerts_section(analyses: Sequence[SymbolAnalysis]) -> list[str]:
    """트리거된 알림 섹션을 생성한다."""
    triggered = [(a.snapshot, alert) for a in analyses for alert in a.alerts]
    if not triggered:
        return ["## 🔔 알림", "", "_오늘 트리거된 신호 없음._", ""]

    lines = ["## 🔔 알림", ""]
    for _snap, alert in triggered:
        sym = alert.symbol_key or "-"
        lines.append(f"- **[{alert.level}] {sym}** — {alert.title}: {alert.body}")
    lines.append("")
    return lines


def _snapshot_table(analyses: Sequence[SymbolAnalysis]) -> list[str]:
    """종목별 지표 스냅샷 테이블을 생성한다."""
    lines = [
        "## 📊 지표 스냅샷",
        "",
        "| 종목 | 종가 | RSI | SMA20 | SMA50 | MACD hist | ATR% | 거래량비 |",
        "|------|------|-----|-------|-------|-----------|------|----------|",
    ]
    for a in sorted(analyses, key=lambda x: x.snapshot.symbol_key):
        s = a.snapshot
        lines.append(
            f"| {s.symbol_key} | {_fmt(s.close, ',.2f')} | {_fmt(s.rsi)} | "
            f"{_fmt(s.sma_short, ',.2f')} | {_fmt(s.sma_long, ',.2f')} | "
            f"{_fmt(s.macd_hist, '.3f')} | {_fmt(s.atr_pct)} | {_fmt(s.volume_ratio, '.2f')} |"
        )
    lines.append("")
    return lines


def build_daily_report(report_date: date, analyses: Sequence[SymbolAnalysis]) -> str:
    """일별 마크다운 리포트를 생성한다.

    Args:
        report_date: 리포트 기준일.
        analyses: 종목별 분석 결과.

    Returns:
        마크다운 문자열.
    """
    total = len(analyses)
    alert_count = sum(len(a.alerts) for a in analyses)

    header = [
        f"# 일별 리포트 — {report_date.isoformat()}",
        "",
        f"- 분석 종목: **{total}**",
        f"- 트리거된 알림: **{alert_count}**",
        "",
    ]

    if total == 0:
        header.append("_분석할 데이터가 없습니다 (수집 이력 부족)._")
        return "\n".join(header)

    sections = header + _alerts_section(analyses) + _snapshot_table(analyses)
    return "\n".join(sections)
