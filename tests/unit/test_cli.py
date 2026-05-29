"""CLI 진입점 테스트 (네트워크 없이 모킹).

argparse 파싱과 collect 명령 경로를 검증한다. run 명령(블로킹 데몬)은
단위 테스트에서 실행하지 않는다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_agent.scheduler.cli import main


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """데이터 디렉토리를 임시 경로로 격리하고 fdr를 모킹한다."""
    monkeypatch.setenv("QA_DATA_DIR", str(tmp_path))
    idx = pd.DatetimeIndex([date(2026, 5, 2)], name="Date")
    frame = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [10]},
        index=idx,
    )
    monkeypatch.setattr(
        "quant_agent.collectors.price.fdr.DataReader",
        lambda *a, **k: frame,
    )


def test_collect_kr_returns_zero():
    """collect --market KR 정상 종료(0)."""
    assert main(["collect", "--market", "KR"]) == 0


def test_collect_all_returns_zero():
    assert main(["collect", "--market", "all"]) == 0


def test_missing_command_exits():
    """서브커맨드 없으면 argparse가 SystemExit."""
    with pytest.raises(SystemExit):
        main([])


def test_all_failure_returns_nonzero(monkeypatch):
    """모든 종목 실패 시 종료 코드 1."""

    def _boom(*a, **k):
        raise ValueError("네트워크 다운")

    monkeypatch.setattr("quant_agent.collectors.price.fdr.DataReader", _boom)
    assert main(["collect", "--market", "KR"]) == 1


def test_analyze_returns_zero():
    """analyze는 데이터가 부족해도(스킵) 정상 종료(0)."""
    assert main(["analyze"]) == 0


def test_daily_returns_zero():
    """daily는 수집 성공 시 0 (분석은 봉 부족으로 스킵되지만 무관)."""
    assert main(["daily"]) == 0


def test_daily_all_collection_failure_returns_nonzero(monkeypatch):
    """daily에서 수집이 전량 실패하면 종료 코드 1."""

    def _boom(*a, **k):
        raise ValueError("네트워크 다운")

    monkeypatch.setattr("quant_agent.collectors.price.fdr.DataReader", _boom)
    assert main(["daily"]) == 1
