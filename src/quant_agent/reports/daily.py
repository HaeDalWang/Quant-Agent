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
from quant_agent.broker.base import Account


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


def _portfolio_section(account: Account, alerted_keys: set[str]) -> list[str]:
    """보유 포트폴리오 섹션을 생성한다.

    보유종목 중 오늘 알림이 트리거된 종목은 🔔로 표시해, 추상적 신호를
    "내가 실제로 들고 있는 종목"과 연결한다 (이 리포트의 핵심 가치).
    """
    lines = [
        "## 💼 내 포트폴리오",
        "",
        f"- 총 자산: **{account.total_assets:,.0f}** "
        f"(현금 {account.cash:,.0f} + 평가 {account.positions_value:,.0f})",
    ]
    total_rate = account.total_pnl_rate
    rate_str = f"{total_rate:+.2f}%" if total_rate is not None else "-"
    lines.append(f"- 평가손익: **{account.total_pnl:+,.0f}** ({rate_str})")
    lines.append("")

    if not account.positions:
        lines.append("_보유 종목이 없습니다._")
        lines.append("")
        return lines

    lines.append("| 종목 | 수량 | 평균단가 | 현재가 | 평가손익 | 수익률 | 신호 |")
    lines.append("|------|------|----------|--------|----------|--------|------|")
    for p in sorted(account.positions, key=lambda x: x.symbol_key):
        rate = f"{p.pnl_rate:+.2f}%" if p.pnl_rate is not None else "-"
        bell = "🔔" if p.symbol_key in alerted_keys else ""
        lines.append(
            f"| {p.symbol_key} | {p.quantity:,.0f} | {p.avg_price:,.2f} | "
            f"{p.current_price:,.2f} | {p.pnl:+,.0f} | {rate} | {bell} |"
        )
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


def build_daily_report(
    report_date: date,
    analyses: Sequence[SymbolAnalysis],
    account: Account | None = None,
) -> str:
    """일별 마크다운 리포트를 생성한다.

    Args:
        report_date: 리포트 기준일.
        analyses: 종목별 분석 결과.
        account: 보유 계좌 스냅샷. 주어지면 포트폴리오 섹션을 추가한다.
            None이면 생략(하위 호환 — 브로커 미연동·조회 실패 시).

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

    sections = header + _alerts_section(analyses)

    # 포트폴리오 섹션 (계좌 주어진 경우). 알림 뜬 보유종목을 🔔로 강조.
    if account is not None:
        alerted_keys = {
            alert.symbol_key for a in analyses for alert in a.alerts if alert.symbol_key
        }
        sections += _portfolio_section(account, alerted_keys)

    sections += _snapshot_table(analyses)
    return "\n".join(sections)
