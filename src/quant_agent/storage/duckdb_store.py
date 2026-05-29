"""DuckDB 기반 저장소 구현.

파일 1개로 시작하는 시계열 저장소. 멱등성은 (symbol_key, dt) 기본키와
INSERT ... ON CONFLICT DO UPDATE로 보장한다.

주의: DuckDB 연결은 동시 쓰기에 안전하지 않다. Phase 0의 순차 실행 스케줄러
환경에서는 문제없으며, 동시성이 필요해지면 그때 대응한다(YAGNI).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from quant_agent.collectors.base import OHLCV_COLUMNS
from quant_agent.storage.base import Store

_OHLCV_TABLE = "ohlcv"

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_OHLCV_TABLE} (
    symbol_key VARCHAR NOT NULL,
    dt         DATE    NOT NULL,
    open       DOUBLE,
    high       DOUBLE,
    low        DOUBLE,
    close      DOUBLE,
    volume     BIGINT,
    PRIMARY KEY (symbol_key, dt)
);
"""

# 멱등 upsert. incoming 뷰에서 표준 컬럼만 선택하며,
# 거래량 NaN은 0으로, dt/close가 없는 비정상 행은 제외한다.
_UPSERT_SQL = f"""
INSERT INTO {_OHLCV_TABLE} (symbol_key, dt, open, high, low, close, volume)
SELECT
    symbol_key,
    dt,
    open, high, low, close,
    COALESCE(TRY_CAST(volume AS BIGINT), 0) AS volume
FROM incoming
WHERE dt IS NOT NULL AND close IS NOT NULL
ON CONFLICT (symbol_key, dt) DO UPDATE SET
    open   = excluded.open,
    high   = excluded.high,
    low    = excluded.low,
    close  = excluded.close,
    volume = excluded.volume;
"""


class DuckDBStore(Store):
    """DuckDB 파일 기반 Store 구현체."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)
        self._con = duckdb.connect(self._path)
        self._con.execute(_CREATE_TABLE_SQL)

    def upsert_ohlcv(self, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0

        missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"OHLCV 스키마 컬럼 누락: {missing}")

        # 표준 컬럼만, 정해진 순서로 전달 (입력 변경 없이 뷰로 등록)
        incoming = df.loc[:, list(OHLCV_COLUMNS)]
        self._con.register("incoming", incoming)
        try:
            self._con.execute(_UPSERT_SQL)
        finally:
            self._con.unregister("incoming")
        return len(incoming)

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        result = self._con.execute(sql, params or [])
        return result.fetchdf()

    def latest_date(self, symbol_key: str) -> str | None:
        row = self._con.execute(
            f"SELECT MAX(dt) FROM {_OHLCV_TABLE} WHERE symbol_key = ?",
            [symbol_key],
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0].isoformat()

    def count(self, symbol_key: str | None = None) -> int:
        if symbol_key is None:
            row = self._con.execute(f"SELECT COUNT(*) FROM {_OHLCV_TABLE}").fetchone()
        else:
            row = self._con.execute(
                f"SELECT COUNT(*) FROM {_OHLCV_TABLE} WHERE symbol_key = ?",
                [symbol_key],
            ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> DuckDBStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
