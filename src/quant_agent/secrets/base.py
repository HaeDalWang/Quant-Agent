"""시크릿 공급자(SecretProvider) 추상 인터페이스.

시크릿이 "어디에" 저장돼 있는가를 추상화한다. 로컬은 .env, 클라우드 배포 시
AWS Secrets Manager처럼 백엔드가 바뀌어도 상위 레이어는 영향받지 않는다.

설계: provider는 시크릿을 dict로 "로드만" 한다. 환경변수 주입·Settings 로드는
bootstrap이 담당한다(관심사 분리). 이 덕분에 기존 Settings(pydantic-settings)를
전혀 손대지 않고도 클라우드 시크릿을 지원할 수 있다.

Collector/Store/AlertChannel과 동일한 인터페이스 패턴이다 — 교체 가능성을
인터페이스가 책임진다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretError(Exception):
    """시크릿 로드 실패."""


class SecretProvider(ABC):
    """시크릿 공급자 인터페이스."""

    @abstractmethod
    def load(self) -> dict[str, str]:
        """시크릿을 키-값 dict로 로드한다.

        Returns:
            환경변수 이름 → 값 매핑. 빈 dict는 "추가 주입할 시크릿 없음"을 뜻한다
            (예: .env/환경변수에 이미 다 있는 로컬 환경).

        Raises:
            SecretError: 백엔드 접근·파싱 실패 시.
        """
        raise NotImplementedError
