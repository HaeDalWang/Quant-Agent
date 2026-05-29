"""수집 서비스 — 종목 단위 장애 격리 + 증분 수집.

배치 수집의 핵심 책임:
1. **장애 격리**: 한 종목의 실패가 전체 배치를 죽이지 않는다. 각 종목을 독립적으로
   처리하고 결과(SymbolResult)를 수집한다.
2. **증분 수집**: 저장소의 최신 거래일 이후만 가져온다. 멱등성과 효율을 함께 확보.
3. **구조화 로깅**: 시작/종료/실패를 로그로 남긴다.

Collector와 Store를 생성자로 주입받아(DI) 테스트 시 모킹할 수 있다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from quant_agent.collectors.base import Collector, CollectorError
from quant_agent.service.results import BatchResult, CollectionStatus, SymbolResult
from quant_agent.storage.base import Store
from quant_agent.universe.models import Symbol

logger = logging.getLogger(__name__)

# 신규 종목의 초기 백필 기간(일). 지표 워밍업을 고려해 약 1년 이상 확보.
DEFAULT_BACKFILL_DAYS = 365


class CollectionService:
    """Tier 1 종목의 일별 OHLCV를 수집·저장한다."""

    def __init__(
        self,
        collector: Collector,
        store: Store,
        backfill_days: int = DEFAULT_BACKFILL_DAYS,
    ) -> None:
        self._collector = collector
        self._store = store
        self._backfill_days = backfill_days

    def collect(self, symbols: Iterable[Symbol], end: date | None = None) -> BatchResult:
        """여러 종목을 장애 격리하며 수집한다.

        Args:
            symbols: 수집 대상 종목들.
            end: 수집 종료일. None이면 오늘.

        Returns:
            각 종목 결과를 담은 BatchResult.
        """
        end = end or date.today()
        symbol_list: Sequence[Symbol] = tuple(symbols)
        logger.info("배치 수집 시작: %d종목, 종료일=%s", len(symbol_list), end)

        results = tuple(self._collect_one(symbol, end) for symbol in symbol_list)
        batch = BatchResult(results=results)

        logger.info("배치 수집 완료: %s", batch.summary())
        for r in batch.failed:
            logger.warning("수집 실패 [%s]: %s", r.symbol_key, r.error)
        return batch

    def _collect_one(self, symbol: Symbol, end: date) -> SymbolResult:
        """단일 종목 수집. 모든 예외를 포착해 FAILED로 격리한다."""
        try:
            start = self._incremental_start(symbol.key, end)
            if start > end:
                logger.debug("[%s] 신규 데이터 없음 (start=%s > end=%s)", symbol.key, start, end)
                return SymbolResult(symbol.key, CollectionStatus.NO_DATA)

            df = self._collector.fetch(symbol, start, end)
            if df.empty:
                logger.debug("[%s] 수집 결과 비어 있음 (%s~%s)", symbol.key, start, end)
                return SymbolResult(symbol.key, CollectionStatus.NO_DATA)

            rows = self._store.upsert_ohlcv(df)
            logger.info("[%s] 저장 완료: %d행 (%s~%s)", symbol.key, rows, start, end)
            return SymbolResult(symbol.key, CollectionStatus.OK, rows=rows)

        except CollectorError as exc:
            return SymbolResult(symbol.key, CollectionStatus.FAILED, error=str(exc))
        except Exception as exc:  # 예기치 못한 오류도 격리 (배치 보호)
            logger.exception("[%s] 예기치 못한 수집 오류", symbol.key)
            return SymbolResult(symbol.key, CollectionStatus.FAILED, error=f"unexpected: {exc}")

    def _incremental_start(self, symbol_key: str, end: date) -> date:
        """저장된 최신 거래일 다음 날을 시작일로 계산한다.

        저장 이력이 없으면 backfill_days만큼 거슬러 올라간 날짜부터.
        """
        latest = self._store.latest_date(symbol_key)
        if latest is None:
            return end - timedelta(days=self._backfill_days)
        return date.fromisoformat(latest) + timedelta(days=1)
