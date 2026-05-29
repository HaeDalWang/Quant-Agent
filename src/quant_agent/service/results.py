"""수집 작업 결과 모델 (불변).

종목 단위 수집 결과와 배치 전체 요약을 표현한다. 장애 격리 결과를 구조화해서
로깅·리포팅·(추후) 에이전트 컨텍스트로 활용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CollectionStatus(StrEnum):
    """종목 단위 수집 상태."""

    OK = "OK"  # 정상 수집·저장
    NO_DATA = "NO_DATA"  # 수집은 성공했으나 신규 데이터 없음 (휴장 등)
    FAILED = "FAILED"  # 수집 실패 (격리됨)


@dataclass(frozen=True, slots=True)
class SymbolResult:
    """한 종목의 수집 결과 (불변)."""

    symbol_key: str
    status: CollectionStatus
    rows: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BatchResult:
    """배치 수집 전체 요약 (불변)."""

    results: tuple[SymbolResult, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def ok(self) -> tuple[SymbolResult, ...]:
        return tuple(r for r in self.results if r.status is CollectionStatus.OK)

    @property
    def failed(self) -> tuple[SymbolResult, ...]:
        return tuple(r for r in self.results if r.status is CollectionStatus.FAILED)

    @property
    def no_data(self) -> tuple[SymbolResult, ...]:
        return tuple(r for r in self.results if r.status is CollectionStatus.NO_DATA)

    @property
    def rows_stored(self) -> int:
        return sum(r.rows for r in self.results)

    def summary(self) -> str:
        """사람이 읽을 수 있는 한 줄 요약."""
        return (
            f"수집 {self.total}종목: 성공={len(self.ok)} "
            f"무데이터={len(self.no_data)} 실패={len(self.failed)} "
            f"(행 {self.rows_stored})"
        )
