"""분석 서비스 테스트 — 와이어링과 장애 격리."""

from __future__ import annotations

import pytest

from quant_agent.alerts.base import Alert, AlertChannel
from quant_agent.analysis.signals import MIN_BARS
from quant_agent.service.analysis import AnalysisService
from quant_agent.storage.duckdb_store import DuckDBStore
from quant_agent.universe.models import Market, Symbol
from tests.conftest import make_ohlcv_series


class FakeChannel(AlertChannel):
    """전송된 알림·리포트를 캡처하는 채널."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []
        self.reports: list[tuple[str, str]] = []

    def send(self, alert: Alert) -> bool:
        self.alerts.append(alert)
        return True

    def send_report(self, title: str, markdown: str) -> bool:
        self.reports.append((title, markdown))
        return True


@pytest.fixture
def store(tmp_path):
    db = DuckDBStore(tmp_path / "analysis.duckdb")
    yield db
    db.close()


def _seed(store, symbol_key: str, closes: list[float], volumes=None) -> None:
    store.upsert_ohlcv(make_ohlcv_series(symbol_key, closes, volumes=volumes))


def test_analysis_sends_report_always(store):
    """분석 후 리포트는 항상 1회 전송된다."""
    channel = FakeChannel()
    _seed(store, "US:AAPL", [float(100 + i) for i in range(MIN_BARS + 5)])
    service = AnalysisService(store, channel)

    result = service.analyze([Symbol("AAPL", "Apple", Market.US)])

    assert len(channel.reports) == 1
    assert len(result.analyses) == 1


def test_analysis_triggers_alert_on_oversold(store):
    """단조 하락 → RSI 과매도 → 알림 전송."""
    channel = FakeChannel()
    # 강한 단조 하락으로 RSI를 과매도로 만든다
    closes = [float(200 - i) for i in range(MIN_BARS + 10)]
    _seed(store, "US:AAPL", closes)
    service = AnalysisService(store, channel)

    service.analyze([Symbol("AAPL", "Apple", Market.US)])

    assert len(channel.alerts) > 0
    assert any("과매도" in a.title for a in channel.alerts)


def test_skips_symbol_with_insufficient_data(store):
    """데이터 부족 종목은 skipped로 분류되고 분석에서 빠진다."""
    channel = FakeChannel()
    _seed(store, "US:AAPL", [100.0] * (MIN_BARS - 1))  # 부족
    service = AnalysisService(store, channel)

    result = service.analyze([Symbol("AAPL", "Apple", Market.US)])

    assert "US:AAPL" in result.skipped
    assert len(result.analyses) == 0


def test_failure_is_isolated(store, monkeypatch):
    """한 종목 분석 실패가 전체 배치를 멈추지 않는다."""
    channel = FakeChannel()
    _seed(store, "US:AAPL", [float(100 + i) for i in range(MIN_BARS + 5)])
    _seed(store, "US:MSFT", [float(100 + i) for i in range(MIN_BARS + 5)])
    service = AnalysisService(store, channel)

    # AAPL 조회 시에만 예외를 던지도록 store.query를 패치
    real_query = store.query

    def flaky_query(sql, params=None):
        if params and params[0] == "US:AAPL":
            raise RuntimeError("의도된 분석 실패")
        return real_query(sql, params)

    monkeypatch.setattr(store, "query", flaky_query)

    result = service.analyze(
        [
            Symbol("AAPL", "Apple", Market.US),
            Symbol("MSFT", "Microsoft", Market.US),
        ]
    )

    # AAPL은 실패, MSFT는 정상 — 리포트는 여전히 전송
    assert "US:AAPL" in result.failed
    assert len(result.analyses) == 1
    assert result.analyses[0].snapshot.symbol_key == "US:MSFT"
    assert len(channel.reports) == 1


def test_summary_format(store):
    channel = FakeChannel()
    _seed(store, "US:AAPL", [float(100 + i) for i in range(MIN_BARS + 5)])
    service = AnalysisService(store, channel)
    result = service.analyze([Symbol("AAPL", "Apple", Market.US)])
    assert "분석" in result.summary()
