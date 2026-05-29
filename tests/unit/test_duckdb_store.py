"""DuckDB 저장소 테스트 — 멱등성이 핵심."""

from __future__ import annotations

from datetime import date

import pytest

from quant_agent.storage.duckdb_store import DuckDBStore
from tests.conftest import make_ohlcv


@pytest.fixture
def store(tmp_path):
    """임시 디렉토리에 DuckDB 파일을 만들어 격리된 저장소를 제공한다."""
    db = DuckDBStore(tmp_path / "test.duckdb")
    yield db
    db.close()


def test_upsert_inserts_rows(store):
    # Arrange
    df = make_ohlcv("KR:005930", [date(2026, 5, 1), date(2026, 5, 2)])

    # Act
    rows = store.upsert_ohlcv(df)

    # Assert
    assert rows == 2
    assert store.count("KR:005930") == 2


def test_upsert_is_idempotent(store):
    """같은 데이터를 두 번 넣어도 행이 중복되지 않는다 (멱등성)."""
    # Arrange
    df = make_ohlcv("KR:005930", [date(2026, 5, 1), date(2026, 5, 2)])

    # Act
    store.upsert_ohlcv(df)
    store.upsert_ohlcv(df)  # 재실행

    # Assert
    assert store.count("KR:005930") == 2  # 4가 아니라 2


def test_upsert_updates_existing_row(store):
    """같은 (symbol_key, dt)는 갱신된다."""
    # Arrange
    day = [date(2026, 5, 1)]
    store.upsert_ohlcv(make_ohlcv("KR:005930", day))

    # Act: 같은 날짜, 다른 종가로 갱신
    updated = make_ohlcv("KR:005930", day)
    updated.loc[0, "close"] = 999.0
    store.upsert_ohlcv(updated)

    # Assert
    result = store.query(
        "SELECT close FROM ohlcv WHERE symbol_key = ? AND dt = ?",
        ["KR:005930", date(2026, 5, 1)],
    )
    assert result.iloc[0]["close"] == 999.0
    assert store.count("KR:005930") == 1


def test_latest_date_returns_max(store):
    # Arrange
    store.upsert_ohlcv(
        make_ohlcv("KR:005930", [date(2026, 5, 1), date(2026, 5, 3), date(2026, 5, 2)])
    )

    # Act / Assert
    assert store.latest_date("KR:005930") == "2026-05-03"


def test_latest_date_none_when_empty(store):
    assert store.latest_date("US:AAPL") is None


def test_upsert_empty_df_is_noop(store):
    import pandas as pd

    assert store.upsert_ohlcv(pd.DataFrame()) == 0
    assert store.count() == 0


def test_upsert_rejects_missing_columns(store):
    import pandas as pd

    bad = pd.DataFrame({"symbol_key": ["KR:005930"], "dt": [date(2026, 5, 1)]})
    with pytest.raises(ValueError, match="컬럼 누락"):
        store.upsert_ohlcv(bad)
