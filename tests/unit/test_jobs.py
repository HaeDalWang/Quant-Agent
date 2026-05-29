"""스케줄러 잡 와이어링 테스트 (네트워크 없이 모킹).

jobs는 Collector/Store/Service를 실제로 조립하므로, 스모크 테스트로
의존성 와이어링과 자기완결 실행(저장소 열기→수집→닫기)을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from quant_agent.config.settings import Settings
from quant_agent.scheduler.jobs import collect_all, collect_market, run_collection
from quant_agent.universe.models import Market, Symbol


def _patch_fdr(monkeypatch) -> None:
    """fdr.DataReader를 단일 행 반환으로 모킹한다."""
    idx = pd.DatetimeIndex([date(2026, 5, 2)], name="Date")
    frame = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [10]},
        index=idx,
    )
    monkeypatch.setattr(
        "quant_agent.collectors.price.fdr.DataReader",
        lambda *a, **k: frame,
    )


def test_run_collection_opens_and_persists(tmp_path, monkeypatch):
    # Arrange
    _patch_fdr(monkeypatch)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    settings.ensure_data_dir()
    symbols = [Symbol("005930", "삼성전자", Market.KR)]

    # Act
    batch = run_collection(settings, symbols, end=date(2026, 5, 2))

    # Assert: 수집 성공 + 파일 실제 생성
    assert len(batch.ok) == 1
    assert settings.duckdb_path.exists()


def test_collect_market_filters_kr(tmp_path, monkeypatch):
    _patch_fdr(monkeypatch)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    settings.ensure_data_dir()

    batch = collect_market(settings, Market.KR)

    # KR Tier1 종목 수만큼 결과
    assert batch.total > 0
    assert len(batch.failed) == 0


def test_collect_all_covers_both_markets(tmp_path, monkeypatch):
    _patch_fdr(monkeypatch)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    settings.ensure_data_dir()

    batch = collect_all(settings)

    assert batch.total > 0
    assert batch.rows_stored > 0
