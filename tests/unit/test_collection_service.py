"""수집 서비스 테스트 — 장애 격리와 증분 수집이 핵심."""

from __future__ import annotations

from datetime import date

import pytest

from quant_agent.service.collection import CollectionService
from quant_agent.service.results import CollectionStatus
from quant_agent.storage.duckdb_store import DuckDBStore
from quant_agent.universe.models import Market, Symbol
from tests.conftest import FakeCollector, make_ohlcv


@pytest.fixture
def store(tmp_path):
    db = DuckDBStore(tmp_path / "svc.duckdb")
    yield db
    db.close()


def test_failure_is_isolated_per_symbol(store):
    """한 종목이 실패해도 나머지 종목은 정상 수집된다 (장애 격리)."""
    # Arrange
    s_ok = Symbol("005930", "삼성전자", Market.KR)
    s_fail = Symbol("000660", "SK하이닉스", Market.KR)
    s_ok2 = Symbol("AAPL", "Apple", Market.US)

    collector = FakeCollector(
        data={
            "KR:005930": make_ohlcv("KR:005930", [date(2026, 5, 1)]),
            "US:AAPL": make_ohlcv("US:AAPL", [date(2026, 5, 1)]),
        },
        fail_keys={"KR:000660"},
    )
    service = CollectionService(collector, store)

    # Act
    batch = service.collect([s_ok, s_fail, s_ok2], end=date(2026, 5, 2))

    # Assert: 실패 1건이 전체를 죽이지 않음
    assert batch.total == 3
    assert len(batch.ok) == 2
    assert len(batch.failed) == 1
    assert batch.failed[0].symbol_key == "KR:000660"
    assert "의도된 실패" in batch.failed[0].error


def test_no_data_when_collector_returns_empty(store):
    """수집 결과가 비면 NO_DATA로 분류된다."""
    # Arrange
    s = Symbol("005930", "삼성전자", Market.KR)
    collector = FakeCollector(data={})  # 빈 결과
    service = CollectionService(collector, store)

    # Act
    batch = service.collect([s], end=date(2026, 5, 2))

    # Assert
    assert len(batch.no_data) == 1
    assert batch.results[0].status is CollectionStatus.NO_DATA


def test_incremental_start_after_latest(store):
    """저장된 최신일 다음 날부터 증분 수집한다."""
    # Arrange: 5/1 데이터가 이미 저장됨
    s = Symbol("005930", "삼성전자", Market.KR)
    store.upsert_ohlcv(make_ohlcv("KR:005930", [date(2026, 5, 1)]))

    captured = {}

    class CapturingCollector(FakeCollector):
        def fetch(self, symbol, start, end):
            captured["start"] = start
            return make_ohlcv(symbol.key, [date(2026, 5, 2)])

    service = CollectionService(CapturingCollector(), store)

    # Act
    service.collect([s], end=date(2026, 5, 2))

    # Assert: 5/1 다음 날인 5/2부터 요청
    assert captured["start"] == date(2026, 5, 2)


def test_backfill_for_new_symbol(store):
    """이력이 없는 신규 종목은 backfill_days만큼 거슬러 수집한다."""
    # Arrange
    s = Symbol("005930", "삼성전자", Market.KR)
    captured = {}

    class CapturingCollector(FakeCollector):
        def fetch(self, symbol, start, end):
            captured["start"] = start
            return make_ohlcv(symbol.key, [end])

    service = CollectionService(CapturingCollector(), store, backfill_days=30)

    # Act
    service.collect([s], end=date(2026, 5, 31))

    # Assert: 30일 전인 5/1부터
    assert captured["start"] == date(2026, 5, 1)


def test_skip_when_already_up_to_date(store):
    """최신일이 종료일 이상이면 수집을 건너뛴다 (NO_DATA)."""
    # Arrange: 5/2까지 저장됨, 종료일도 5/2
    s = Symbol("005930", "삼성전자", Market.KR)
    store.upsert_ohlcv(make_ohlcv("KR:005930", [date(2026, 5, 2)]))
    service = CollectionService(FakeCollector(), store)

    # Act
    batch = service.collect([s], end=date(2026, 5, 2))

    # Assert
    assert batch.results[0].status is CollectionStatus.NO_DATA
