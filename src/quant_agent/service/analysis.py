"""분석 서비스 — 저장소 → 지표 → 규칙 → 알림/리포트 와이어링.

Phase 1의 핵심 루프:
1. 저장소에서 각 종목의 OHLCV 이력을 읽는다.
2. 최신 봉 지표 스냅샷을 계산한다.
3. 규칙을 평가해 트리거된 알림을 채널로 전송한다.
4. 종목별 분석을 모아 일별 리포트를 생성·전송한다.

수집 서비스와 동일하게 종목 단위 장애 격리를 적용한다 — 한 종목 분석 실패가
전체 배치를 멈추지 않는다. Store와 AlertChannel을 주입받아(DI) 테스트 시 모킹한다.

LLM은 채널이 아니라 저장소를 읽는다는 원칙대로, 이 서비스는 저장소에서 직접
데이터를 읽어 결정론적으로 분석한다(AI 경계 아래).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from quant_agent.alerts.base import AlertChannel
from quant_agent.alerts.rules import DEFAULT_RULES, Rule, evaluate
from quant_agent.analysis.signals import compute_snapshot
from quant_agent.broker.base import Account, Broker
from quant_agent.reports.daily import SymbolAnalysis, build_daily_report
from quant_agent.storage.base import Store
from quant_agent.universe.models import Symbol

logger = logging.getLogger(__name__)

# 지표 계산에 필요한 충분한 이력 (SMA50 + MACD 워밍업 여유)
_LOOKBACK_LIMIT = 250


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """분석 배치 결과 (불변)."""

    analyses: tuple[SymbolAnalysis, ...] = field(default_factory=tuple)
    skipped: tuple[str, ...] = field(default_factory=tuple)  # 데이터 부족 종목 키
    failed: tuple[str, ...] = field(default_factory=tuple)  # 분석 실패 종목 키

    @property
    def alert_count(self) -> int:
        return sum(len(a.alerts) for a in self.analyses)

    def summary(self) -> str:
        return (
            f"분석 {len(self.analyses)}종목: 알림={self.alert_count} "
            f"스킵={len(self.skipped)} 실패={len(self.failed)}"
        )


class AnalysisService:
    """저장된 OHLCV를 분석해 알림·리포트를 생성한다."""

    def __init__(
        self,
        store: Store,
        channel: AlertChannel,
        rules: tuple[Rule, ...] = DEFAULT_RULES,
        broker: Broker | None = None,
    ) -> None:
        self._store = store
        self._channel = channel
        self._rules = rules
        self._broker = broker

    def analyze(self, symbols: Iterable[Symbol], report_date: date | None = None) -> AnalysisResult:
        """종목들을 분석하고 알림 전송 + 리포트 생성한다 (장애 격리)."""
        report_date = report_date or date.today()
        analyses: list[SymbolAnalysis] = []
        skipped: list[str] = []
        failed: list[str] = []

        for symbol in symbols:
            try:
                analysis = self._analyze_one(symbol)
                if analysis is None:
                    skipped.append(symbol.key)
                    continue
                analyses.append(analysis)
                self._send_alerts(analysis)
            except Exception:  # 종목 단위 격리 (트레이스백은 logger.exception이 기록)
                logger.exception("[%s] 분석 실패", symbol.key)
                failed.append(symbol.key)

        result = AnalysisResult(
            analyses=tuple(analyses),
            skipped=tuple(skipped),
            failed=tuple(failed),
        )
        self._send_report(report_date, result)
        logger.info("분석 완료: %s", result.summary())
        return result

    def _analyze_one(self, symbol: Symbol) -> SymbolAnalysis | None:
        """단일 종목 분석. 데이터 부족이면 None."""
        df = self._store.query(
            "SELECT * FROM ohlcv WHERE symbol_key = ? ORDER BY dt DESC LIMIT ?",
            [symbol.key, _LOOKBACK_LIMIT],
        )
        snapshot = compute_snapshot(df, symbol.key)
        if snapshot is None:
            logger.debug("[%s] 데이터 부족으로 분석 스킵", symbol.key)
            return None
        alerts = tuple(evaluate(snapshot, self._rules))
        return SymbolAnalysis(snapshot=snapshot, alerts=alerts)

    def _send_alerts(self, analysis: SymbolAnalysis) -> None:
        """트리거된 알림을 채널로 전송한다."""
        for alert in analysis.alerts:
            self._channel.send(alert)

    def _fetch_account(self) -> Account | None:
        """브로커에서 계좌를 조회한다. 실패는 격리한다(None 반환).

        브로커 조회 실패(KIS 인증·네트워크 등)가 시장 분석 리포트 전송을
        막아서는 안 된다 — 계좌 없이 리포트는 그대로 나간다.
        """
        if self._broker is None:
            return None
        try:
            return self._broker.get_account()
        except Exception:
            logger.exception("계좌 조회 실패 — 포트폴리오 없이 리포트 생성")
            return None

    def _send_report(self, report_date: date, result: AnalysisResult) -> None:
        """일별 리포트를 생성·전송한다 (계좌 있으면 포트폴리오 포함)."""
        account = self._fetch_account()
        markdown = build_daily_report(report_date, result.analyses, account=account)
        title = f"일별 리포트 {report_date.isoformat()}"
        self._channel.send_report(title, markdown)
