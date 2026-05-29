"""FinanceDataReader 기반 가격 수집기.

FinanceDataReader는 단일 API로 KR(KOSPI/KOSDAQ)과 US(NYSE/NASDAQ) 시세를 모두
커버한다. 반환 형식(DatetimeIndex + Open/High/Low/Close/Volume)을 표준 OHLCV
스키마로 정규화한다.

추후 KIS/Alpaca 등 실거래 API를 추가해도 Collector 인터페이스는 불변이므로
상위 레이어는 영향받지 않는다.
"""

from __future__ import annotations

from datetime import date

import FinanceDataReader as fdr  # noqa: N813  (라이브러리 표준 별칭)
import pandas as pd

from quant_agent.collectors.base import (
    OHLCV_COLUMNS,
    Collector,
    CollectorError,
    empty_ohlcv,
)
from quant_agent.universe.models import Market, Symbol

# FinanceDataReader 원본 컬럼 → 표준 스키마 매핑
_FDR_COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


class FinanceDataReaderCollector(Collector):
    """FinanceDataReader 어댑터. KR·US 모두 지원."""

    _SUPPORTED = frozenset({Market.KR, Market.US})

    def supports(self, market: Market) -> bool:
        return market in self._SUPPORTED

    def fetch(self, symbol: Symbol, start: date, end: date) -> pd.DataFrame:
        if not self.supports(symbol.market):
            raise CollectorError(f"지원하지 않는 시장입니다: {symbol.market} ({symbol.key})")

        try:
            raw = fdr.DataReader(symbol.code, start, end)
        except Exception as exc:  # FDR 내부 예외를 도메인 예외로 변환
            raise CollectorError(f"시세 수집 실패: {symbol.key} ({start}~{end}): {exc}") from exc

        return self._normalize(raw, symbol)

    def _normalize(self, raw: pd.DataFrame, symbol: Symbol) -> pd.DataFrame:
        """FDR 원본 DataFrame을 표준 OHLCV 스키마로 변환한다 (불변).

        입력 raw를 변경하지 않고 새 DataFrame을 반환한다.
        """
        if raw is None or raw.empty:
            return empty_ohlcv()

        # 입력을 변경하지 않기 위해 복사 후 작업
        df = raw.copy()

        # 거래일: DatetimeIndex → date 컬럼
        df = df.reset_index()
        # reset_index 후 날짜 컬럼명은 보통 'Date' 또는 'index'
        date_col = df.columns[0]
        df = df.rename(columns={date_col: "dt", **_FDR_COLUMN_MAP})
        df["dt"] = pd.to_datetime(df["dt"]).dt.date

        # 종목 식별자 부여
        df["symbol_key"] = symbol.key

        # 필수 컬럼 누락 검증 (소스 스키마 변경 방어)
        missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
        if missing:
            raise CollectorError(f"수집 데이터에 필수 컬럼이 없습니다: {symbol.key} 누락={missing}")

        # 표준 컬럼만, 정해진 순서로 반환
        return df.loc[:, list(OHLCV_COLUMNS)].reset_index(drop=True)
