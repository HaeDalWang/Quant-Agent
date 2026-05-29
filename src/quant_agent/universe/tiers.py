"""종목 유니버스 티어 정의.

Tier 1: 수동 큐레이션한 코어 종목 (항상 추적). 유동성·변동성이 검증된 이름.
Tier 2: 조건 기반 동적 스캔 (Phase 1의 screener가 담당, 여기서는 미구현).

스윙/단기(최대 2~3개월) 전략에 맞춰, 유동성이 풍부하고 변동성 스윗스팟에 있는
대형주·ETF 중심으로 구성한다. 자세한 선정 기준은 docs/universe-strategy.md 참고.

이 목록은 출발점이며 고정이 아니다. 실제 변동성·유동성 데이터로 검증 후 조정한다.
"""

from __future__ import annotations

from quant_agent.universe.models import Market, Symbol

# --- US 코어 ---
_US_CORE: tuple[Symbol, ...] = (
    # 메가캡 테크
    Symbol("NVDA", "NVIDIA", Market.US),
    Symbol("AAPL", "Apple", Market.US),
    Symbol("MSFT", "Microsoft", Market.US),
    Symbol("AMZN", "Amazon", Market.US),
    Symbol("META", "Meta Platforms", Market.US),
    Symbol("GOOGL", "Alphabet", Market.US),
    # 고변동 성장주
    Symbol("TSLA", "Tesla", Market.US),
    Symbol("AMD", "Advanced Micro Devices", Market.US),
    Symbol("PLTR", "Palantir", Market.US),
    # 고베타/테마
    Symbol("COIN", "Coinbase", Market.US),
    Symbol("MSTR", "MicroStrategy", Market.US),
    # 섹터/지수 ETF
    Symbol("SPY", "SPDR S&P 500 ETF", Market.US),
    Symbol("QQQ", "Invesco QQQ Trust", Market.US),
    Symbol("SMH", "VanEck Semiconductor ETF", Market.US),
    Symbol("XLE", "Energy Select Sector SPDR", Market.US),
    Symbol("XLF", "Financial Select Sector SPDR", Market.US),
)

# --- KR 코어 ---
_KR_CORE: tuple[Symbol, ...] = (
    # 대형 코어
    Symbol("005930", "삼성전자", Market.KR),
    Symbol("000660", "SK하이닉스", Market.KR),
    Symbol("005380", "현대차", Market.KR),
    # 변동성 중대형 (대표 유동주)
    Symbol("373220", "LG에너지솔루션", Market.KR),
    Symbol("207940", "삼성바이오로직스", Market.KR),
    # ETF
    Symbol("069500", "KODEX 200", Market.KR),
    Symbol("122630", "KODEX 레버리지", Market.KR),
)

# 전체 Tier 1 (불변)
TIER1_CORE: tuple[Symbol, ...] = _US_CORE + _KR_CORE


def tier1_symbols(market: Market | None = None) -> tuple[Symbol, ...]:
    """Tier 1 코어 종목을 반환한다.

    Args:
        market: 지정하면 해당 시장만 필터링. None이면 전체.

    Returns:
        조건에 맞는 종목 튜플 (불변).
    """
    if market is None:
        return TIER1_CORE
    return tuple(s for s in TIER1_CORE if s.market == market)
