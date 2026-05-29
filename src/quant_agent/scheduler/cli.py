"""CLI 진입점.

네 가지 실행 모드를 제공한다:
- `collect`: 수집을 1회 실행하고 종료한다. 테스트·GitHub Actions·Lambda에 적합.
- `analyze`: 저장된 데이터를 분석해 알림·리포트를 1회 생성하고 종료한다.
- `daily`: 수집(KR+US)+분석을 한 번에 실행한다. 노트북에서 하루 한 번 수동 운영용.
- `run`: APScheduler 데몬을 띄워 장마감 시각마다 수집·분석한다. 로컬 상시 실행에 적합.

같은 잡(scheduler.jobs)을 모드들이 공유하므로, 트리거 방식이 바뀌어도 로직은 불변.
"""

from __future__ import annotations

import argparse
import logging
import sys

from quant_agent.config.logging_setup import setup_logging
from quant_agent.config.settings import Settings, load_settings
from quant_agent.scheduler.jobs import (
    analyze_all,
    collect_all,
    collect_market,
)
from quant_agent.universe.models import Market

logger = logging.getLogger(__name__)

# 장마감 후 수집 시각 (Asia/Seoul 기준).
# KR 정규장 마감 15:30 → 16:00 수집. US 정규장 마감(ET 16:00) → 익일 아침 KST.
_KR_HOUR, _KR_MINUTE = 16, 0
_US_HOUR, _US_MINUTE = 7, 0
# 분석은 양 시장 수집이 끝난 뒤 (US 수집 07:00 직후) 실행.
_ANALYZE_HOUR, _ANALYZE_MINUTE = 7, 30
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


def _cmd_analyze(args: argparse.Namespace, settings: Settings) -> int:
    """분석 1회 실행 — 알림·리포트 생성."""
    result = analyze_all(settings)
    print(result.summary())
    return 0


def _cmd_daily(args: argparse.Namespace, settings: Settings) -> int:
    """수집(KR+US) → 분석을 한 번에 실행한다.

    일봉은 그날 한 번만 받으면 되므로, 노트북에서 하루 한 번 수동 실행하기에 적합하다.
    수집이 일부 실패해도 분석은 저장된 데이터로 진행한다(부분 가용성).
    """
    batch = collect_all(settings)
    print(batch.summary())

    result = analyze_all(settings)
    print(result.summary())

    # 수집이 전량 실패하면 비정상 종료 (모니터링이 감지하도록). 분석은 그래도 시도됨.
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
    # 분석: 평일 07:30 (양 시장 수집 직후) — 알림·리포트 생성
    scheduler.add_job(
        lambda: analyze_all(settings),
        CronTrigger(day_of_week="tue-sat", hour=_ANALYZE_HOUR, minute=_ANALYZE_MINUTE),
        id="analyze",
        name="Tier1 분석·알림·리포트",
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
        description="Quant-Agent 수집·분석·알림 파이프라인",
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

    p_analyze = sub.add_parser("analyze", help="저장된 데이터를 분석해 알림·리포트를 1회 생성")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_daily = sub.add_parser("daily", help="수집(KR+US)+분석을 한 번에 실행 (수동 일일 운영)")
    p_daily.set_defaults(func=_cmd_daily)

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
