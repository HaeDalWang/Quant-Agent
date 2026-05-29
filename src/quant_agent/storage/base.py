"""저장소(Store) 추상 인터페이스.

데이터가 "어디에" 쌓이는가를 추상화한다. 초기 구현은 DuckDB(파일 1개)지만,
규모가 커지면 TimescaleDB 등으로 교체해도 상위 레이어는 영향받지 않는다.

핵심 계약: upsert는 멱등(idempotent)하다. 같은 데이터를 두 번 넣어도 중복이 생기지
않는다 — 비기능 요구사항 "잡을 두 번 돌려도 중복 없이 멱등하게 저장된다."
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Store(ABC):
    """시계열 저장소 인터페이스 (Repository 패턴)."""

    @abstractmethod
    def upsert_ohlcv(self, df: pd.DataFrame) -> int:
        """OHLCV 데이터를 멱등 저장한다.

        자연키 (symbol_key, dt) 기준으로 이미 존재하는 행은 갱신, 없으면 삽입한다.

        Args:
            df: OHLCV_COLUMNS 스키마를 따르는 DataFrame.

        Returns:
            저장(삽입+갱신) 시도된 행 수.
        """
        raise NotImplementedError

    @abstractmethod
    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """읽기 전용 SQL을 실행하고 결과를 DataFrame으로 반환한다.

        params를 사용한 파라미터 바인딩을 지원한다 (SQL 인젝션 방지).
        """
        raise NotImplementedError

    @abstractmethod
    def latest_date(self, symbol_key: str) -> str | None:
        """해당 종목의 가장 최근 거래일(ISO 문자열)을 반환한다. 없으면 None."""
        raise NotImplementedError

    @abstractmethod
    def count(self, symbol_key: str | None = None) -> int:
        """저장된 OHLCV 행 수. symbol_key 지정 시 해당 종목만."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """연결을 닫는다."""
        raise NotImplementedError
