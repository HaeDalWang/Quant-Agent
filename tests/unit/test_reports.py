"""일별 리포트 생성 테스트."""

from __future__ import annotations

from datetime import date

from quant_agent.alerts.base import Alert, AlertLevel
from quant_agent.analysis.signals import IndicatorSnapshot
from quant_agent.broker.base import Account, Position
from quant_agent.reports.daily import SymbolAnalysis, build_daily_report
from quant_agent.universe.models import Market, Symbol


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


# --- 포트폴리오 섹션 ---


def _position(code: str, qty: float, avg: float, cur: float) -> Position:
    return Position(
        symbol=Symbol(code, code, Market.US),
        quantity=qty,
        avg_price=avg,
        current_price=cur,
    )


def test_report_omits_portfolio_when_no_account():
    """account 미제공 시 포트폴리오 섹션이 없다 (하위 호환)."""
    analyses = [SymbolAnalysis(snapshot=_snap("US:AAPL"), alerts=())]
    md = build_daily_report(date(2026, 5, 1), analyses)
    assert "내 포트폴리오" not in md


def test_report_includes_portfolio_when_account_given():
    analyses = [SymbolAnalysis(snapshot=_snap("US:AAPL"), alerts=())]
    account = Account(cash=1000.0, positions=(_position("AAPL", 10, 300.0, 312.0),))
    md = build_daily_report(date(2026, 5, 1), analyses, account=account)
    assert "내 포트폴리오" in md
    assert "총 자산" in md
    assert "US:AAPL" in md


def test_report_portfolio_empty_positions():
    analyses = [SymbolAnalysis(snapshot=_snap("US:AAPL"), alerts=())]
    account = Account(cash=5000.0)
    md = build_daily_report(date(2026, 5, 1), analyses, account=account)
    assert "내 포트폴리오" in md
    assert "보유 종목이 없습니다" in md


def test_report_portfolio_marks_alerted_holding():
    """보유종목 중 알림 뜬 종목은 🔔로 표시된다."""
    analyses = [
        SymbolAnalysis(
            snapshot=_snap("US:AAPL"),
            alerts=(Alert("RSI 과매수", "RSI=78", AlertLevel.WARNING, "US:AAPL"),),
        ),
        SymbolAnalysis(snapshot=_snap("US:MSFT"), alerts=()),
    ]
    account = Account(
        cash=1000.0,
        positions=(
            _position("AAPL", 10, 300.0, 312.0),  # 알림 있음 → 🔔
            _position("MSFT", 5, 400.0, 410.0),  # 알림 없음
        ),
    )
    md = build_daily_report(date(2026, 5, 1), analyses, account=account)
    # 포트폴리오 표에서 AAPL 행에만 🔔
    portfolio_part = md[md.index("내 포트폴리오") :]
    aapl_line = next(ln for ln in portfolio_part.splitlines() if "US:AAPL" in ln)
    msft_line = next(ln for ln in portfolio_part.splitlines() if "US:MSFT" in ln)
    assert "🔔" in aapl_line
    assert "🔔" not in msft_line
