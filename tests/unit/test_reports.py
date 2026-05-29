"""일별 리포트 생성 테스트."""

from __future__ import annotations

from datetime import date

from quant_agent.alerts.base import Alert, AlertLevel
from quant_agent.analysis.signals import IndicatorSnapshot
from quant_agent.reports.daily import SymbolAnalysis, build_daily_report


def _snap(symbol_key: str, **overrides) -> IndicatorSnapshot:
    base = dict(
        symbol_key=symbol_key,
        dt=date(2026, 5, 1),
        close=100.0,
        sma_short=98.0,
        sma_long=95.0,
        rsi=45.0,
        macd_line=0.5,
        macd_signal=0.3,
        macd_hist=0.2,
        macd_hist_prev=0.1,
        atr=2.0,
        atr_pct=2.0,
        volume=1000.0,
        avg_volume=900.0,
        volume_ratio=1.1,
    )
    base.update(overrides)
    return IndicatorSnapshot(**base)


def test_empty_report_states_no_data():
    md = build_daily_report(date(2026, 5, 1), [])
    assert "데이터가 없습니다" in md
    assert "2026-05-01" in md


def test_report_includes_header_counts():
    analyses = [
        SymbolAnalysis(
            snapshot=_snap("US:AAPL"),
            alerts=(Alert("RSI 과매도", "RSI=25", AlertLevel.SIGNAL, "US:AAPL"),),
        ),
        SymbolAnalysis(snapshot=_snap("US:MSFT"), alerts=()),
    ]
    md = build_daily_report(date(2026, 5, 1), analyses)
    assert "분석 종목: **2**" in md
    assert "트리거된 알림: **1**" in md


def test_report_shows_no_alerts_message():
    analyses = [SymbolAnalysis(snapshot=_snap("US:AAPL"), alerts=())]
    md = build_daily_report(date(2026, 5, 1), analyses)
    assert "트리거된 신호 없음" in md


def test_report_lists_triggered_alerts():
    analyses = [
        SymbolAnalysis(
            snapshot=_snap("US:AAPL"),
            alerts=(Alert("RSI 과매도", "RSI=25.0", AlertLevel.SIGNAL, "US:AAPL"),),
        ),
    ]
    md = build_daily_report(date(2026, 5, 1), analyses)
    assert "US:AAPL" in md
    assert "RSI 과매도" in md
    assert "RSI=25.0" in md


def test_report_snapshot_table_handles_none():
    """None 지표값은 테이블에서 '-'로 표시된다."""
    analyses = [
        SymbolAnalysis(
            snapshot=_snap("US:AAPL", rsi=None, atr_pct=None),
            alerts=(),
        )
    ]
    md = build_daily_report(date(2026, 5, 1), analyses)
    assert "지표 스냅샷" in md
    assert "| - |" in md  # None이 '-'로 렌더링됨


def test_report_table_sorted_by_symbol():
    analyses = [
        SymbolAnalysis(snapshot=_snap("US:MSFT"), alerts=()),
        SymbolAnalysis(snapshot=_snap("US:AAPL"), alerts=()),
    ]
    md = build_daily_report(date(2026, 5, 1), analyses)
    # AAPL이 MSFT보다 먼저 나와야 함
    assert md.index("US:AAPL") < md.index("US:MSFT")
