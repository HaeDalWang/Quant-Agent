"""수집 잡 정의 — 의존성 와이어링 + 자기완결 실행.

각 잡은 저장소를 열고, 수집하고, 닫는 것까지 한 번에 처리한다(self-contained).
이 설계 덕분에 로컬 APScheduler, GitHub Actions, Lambda 어디서 호출하든 동일하게
동작한다 — 트리거가 바뀌어도 이 함수는 불변.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date

from quant_agent.collectors.price import FinanceDataReaderCollector
from quant_agent.config.settings import Settings
from quant_agent.service.collection import CollectionService
from quant_agent.service.results import BatchResult
from quant_agent.storage.duckdb_store import DuckDBStore
from quant_agent.universe.models import Market, Symbol
from quant_agent.universe.tiers import tier1_symbols

logger = logging.getLogger(__name__)


def run_collection(
    settings: Settings,
    symbols: Iterable[Symbol],
    end: date | None = None,
) -> BatchResult:
    """주어진 종목들에 대해 수집을 1회 실행한다 (자기완결).

    저장소 연결을 열고 수집 후 닫는다. 어떤 트리거에서 호출하든 안전하다.
    """
    collector = FinanceDataReaderCollector()
    with DuckDBStore(settings.duckdb_path) as store:
        service = CollectionService(collector, store)
        return service.collect(symbols, end=end)


def collect_market(settings: Settings, market: Market) -> BatchResult:
    """특정 시장의 Tier 1 종목을 수집한다.

    시장별로 분리해 호출하면 스케줄러가 KR/US를 각 장마감 시각에 맞춰
    독립적으로 트리거할 수 있다.
    """
    symbols = tier1_symbols(market)
    logger.info("시장 수집 시작: %s (%d종목)", market.value, len(symbols))
    return run_collection(settings, symbols)


def collect_all(settings: Settings) -> BatchResult:
    """전체 Tier 1 종목(KR+US)을 한 번에 수집한다."""
    return run_collection(settings, tier1_symbols())
