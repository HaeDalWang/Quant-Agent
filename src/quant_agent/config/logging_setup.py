"""로깅 설정.

모든 잡의 시작/종료/실패를 일관된 형식으로 남긴다. 비기능 요구사항:
"모든 잡은 시작/종료/실패를 구조화 로그로 남긴다."
"""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """루트 로거를 설정한다. 진입점에서 1회 호출한다."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    # 외부 라이브러리의 과도한 로그 억제
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
