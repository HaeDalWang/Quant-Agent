"""종목 유니버스의 값 객체.

시장(KR/US)과 종목을 표현하는 불변 모델. 시장 차이를 여기서 흡수해서
상위 레이어(collectors, storage)가 시장에 무관하게 동작하도록 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Market(StrEnum):
    """대상 시장."""

    KR = "KR"  # 한국 (KOSPI/KOSDAQ)
    US = "US"  # 미국 (NYSE/NASDAQ)


@dataclass(frozen=True, slots=True)
class Symbol:
    """추적 대상 종목 (불변).

    Attributes:
        code: 종목 코드. KR은 6자리 숫자("005930"), US는 티커("AAPL").
        name: 사람이 읽을 수 있는 이름.
        market: 소속 시장.
    """

    code: str
    name: str
    market: Market

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("종목 코드는 비어 있을 수 없습니다.")
        if not isinstance(self.market, Market):
            raise TypeError(f"market은 Market 타입이어야 합니다: {self.market!r}")

    @property
    def key(self) -> str:
        """저장소에서 종목을 구분하는 고유 키 (예: 'KR:005930')."""
        return f"{self.market.value}:{self.code}"
