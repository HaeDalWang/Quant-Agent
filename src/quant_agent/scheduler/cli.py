"""CLI 진입점.

두 가지 실행 모드를 제공한다:
- `collect`: 수집을 1회 실행하고 종료한다. 테스트·GitHub Actions·Lambda에 적합.
- `run`: APScheduler 데몬을 띄워 장마감 시각마다 수집한다. 로컬 상시 실행에 적합.

같은 잡(scheduler.jobs)을 양쪽이 공유하므로, 트리거 방식이 바뀌어도 수집 로직은 불변.
"""

from __future__ import annotations

import argparse
import logging
import sys

from quant_agent.config.logging_setup import setup_logging
from quant_agent.config.settings import Settings, load_settings
from quant_agent.scheduler.jobs import collect_all, collect_market
from quant_agent.universe.models import Market

logger = logging.getLogger(__name__)

# 장마감 후 수집 시각 (Asia/Seoul 기준).
# KR 정규장 마감 15:30 → 16:00 수집. US 정규장 마감(ET 16:00) → 익일 아침 KST.
_KR_HOUR, _KR_MINUTE = 16, 0
_US_HOUR, _US_MINUTE = 7, 0
_TIMEZONE = "Asia/Seoul"


def _cmd_collect(args: argparse.Namespace, settings: Settings) -> int:
    """수집 1회 실행."""
    if args.market == "KR":
        batch = collect_market(settings, Market.KR)
    elif args.market == "US":
        batch = collect_market(settings, Market.US)
    else:
        batch = collect_all(settings)

    print(batch.summary())
    # 모든 종목이 실패하면 비정상 종료 코드 반환 (CI·모니터링이 감지하도록)
    if batch.total > 0 and len(batch.failed) == batch.total:
        logger.error("모든 종목 수집 실패")
        return 1
    return 0


def _cmd_run(args: argparse.Namespace, settings: Settings) -> int:
    """APScheduler 데몬 실행 (상시)."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone=_TIMEZONE)

    # KR: 평일 16:00, US: 평일 07:00 (전일 미국장 마감분)
    scheduler.add_job(
        lambda: collect_market(settings, Market.KR),
        CronTrigger(day_of_week="mon-fri", hour=_KR_HOUR, minute=_KR_MINUTE),
        id="collect_kr",
        name="KR Tier1 수집",
    )
    scheduler.add_job(
        lambda: collect_market(settings, Market.US),
        CronTrigger(day_of_week="tue-sat", hour=_US_HOUR, minute=_US_MINUTE),
        id="collect_us",
        name="US Tier1 수집",
    )

    logger.info("스케줄러 시작 (timezone=%s). 종료하려면 Ctrl+C.", _TIMEZONE)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-agent",
        description="Quant-Agent 데이터 수집 파이프라인 (Phase 0)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="수집을 1회 실행하고 종료")
    p_collect.add_argument(
        "--market",
        choices=["KR", "US", "all"],
        default="all",
        help="수집 대상 시장 (기본: all)",
    )
    p_collect.set_defaults(func=_cmd_collect)

    p_run = sub.add_parser("run", help="스케줄러 데몬 실행 (상시)")
    p_run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. pyproject.toml의 [project.scripts]가 이 함수를 호출한다."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = load_settings()
    setup_logging(settings.log_level)

    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
