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


def test_incremental_start_includes_trailing_overlap(store):
    """저장된 최신일에서 overlap만큼 거슬러 재수집한다 (잠정 거래량 자가 교정)."""
    # Arrange: 5/10 데이터가 이미 저장됨
    s = Symbol("005930", "삼성전자", Market.KR)
    store.upsert_ohlcv(make_ohlcv("KR:005930", [date(2026, 5, 10)]))

    captured = {}

    class CapturingCollector(FakeCollector):
        def fetch(self, symbol, start, end):
            captured["start"] = start
            return make_ohlcv(symbol.key, [end])

    service = CollectionService(CapturingCollector(), store, trailing_overlap_days=5)

    # Act
    service.collect([s], end=date(2026, 5, 12))

    # Assert: 최신일 5/10에서 5일 거슬러 5/5부터 (다음 날이 아니라 겹쳐서)
    assert captured["start"] == date(2026, 5, 5)


def test_trailing_refetch_overwrites_provisional_volume(store):
    """이미 저장된 최근 봉을 다시 받아 잠정 거래량을 확정값으로 덮어쓴다 (멱등)."""
    # Arrange: 5/1을 장초반 잠정 거래량(100)으로 저장 — KR 9시 수집 버그 재현
    s = Symbol("005930", "삼성전자", Market.KR)
    prov = make_ohlcv("KR:005930", [date(2026, 5, 1)])
    prov.loc[0, "volume"] = 100
    store.upsert_ohlcv(prov)

    # 다음 수집에서 collector가 5/1을 확정 거래량(99999)으로 다시 준다
    class CorrectingCollector(FakeCollector):
        def fetch(self, symbol, start, end):
            df = make_ohlcv(symbol.key, [date(2026, 5, 1)])
            df.loc[0, "volume"] = 99999
            return df

    service = CollectionService(CorrectingCollector(), store, trailing_overlap_days=5)

    # Act
    service.collect([s], end=date(2026, 5, 1))

    # Assert: 잠정값 100 → 확정값 99999로 자가 교정됨
    row = store.query("SELECT volume FROM ohlcv WHERE symbol_key='KR:005930' AND dt='2026-05-01'")
    assert int(row.iloc[0]["volume"]) == 99999


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


def test_refetches_trailing_window_even_when_up_to_date(store):
    """최신 상태여도 trailing window를 다시 받는다 (잠정값 자가 교정).

    예전엔 '최신일 이상이면 NO_DATA로 스킵'이 정답이었으나, 그게 바로 KR 장초반
    잠정 거래량이 영영 굳던 버그의 원인이었다. 이제는 항상 최근 며칠을 재수집한다.
    """
    # Arrange: 5/2까지 저장됨, 종료일도 5/2
    s = Symbol("005930", "삼성전자", Market.KR)
    store.upsert_ohlcv(make_ohlcv("KR:005930", [date(2026, 5, 2)]))

    captured = {}

    class CapturingCollector(FakeCollector):
        def fetch(self, symbol, start, end):
            captured["called"] = True
            return make_ohlcv(symbol.key, [date(2026, 5, 2)])

    service = CollectionService(CapturingCollector(), store, trailing_overlap_days=5)

    # Act
    batch = service.collect([s], end=date(2026, 5, 2))

    # Assert: 스킵하지 않고 재수집한다
    assert captured.get("called") is True
    assert batch.results[0].status is CollectionStatus.OK
