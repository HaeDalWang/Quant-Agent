"""데이터 수집기(Collector) 추상 인터페이스.

데이터가 "어디서" 오는가를 추상화한다. 소스(FinanceDataReader, 추후 KIS/Alpaca)가
바뀌어도 이 인터페이스는 불변. 상위 레이어는 구현체가 아니라 인터페이스에 의존한다.

표준 OHLCV 스키마를 정의해서, 어떤 소스를 쓰든 저장소·분석 레이어가 동일한
컬럼 구조를 받도록 정규화한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from quant_agent.universe.models import Market, Symbol

# 표준 OHLCV 컬럼. 모든 Collector 구현체는 이 스키마로 정규화해 반환한다.
# 'symbol_key'로 종목을 식별하고, 'dt'는 거래일(date).
OHLCV_COLUMNS: tuple[str, ...] = (
    "symbol_key",
    "dt",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class CollectorError(Exception):
    """수집 실패. 종목 단위 장애 격리를 위해 service 레이어에서 포착한다."""


class Collector(ABC):
    """가격 데이터 수집기 인터페이스 (Repository 패턴)."""

    @abstractmethod
    def supports(self, market: Market) -> bool:
        """이 수집기가 해당 시장을 처리할 수 있는지 여부."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, symbol: Symbol, start: date, end: date) -> pd.DataFrame:
        """종목의 일별 OHLCV를 가져온다.

        Args:
            symbol: 대상 종목.
            start: 조회 시작일 (포함).
            end: 조회 종료일 (포함).

        Returns:
            OHLCV_COLUMNS 스키마를 따르는 새 DataFrame (불변 — 입력을 변경하지 않음).
            데이터가 없으면 빈 DataFrame(컬럼은 유지)을 반환한다.

        Raises:
            CollectorError: 수집 자체가 실패한 경우 (네트워크·소스 오류 등).
        """
        raise NotImplementedError


def empty_ohlcv() -> pd.DataFrame:
    """OHLCV 스키마를 가진 빈 DataFrame을 반환한다."""
    return pd.DataFrame(columns=list(OHLCV_COLUMNS))
