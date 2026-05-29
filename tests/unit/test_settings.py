"""설정 로드 및 시작 시 검증(fail-fast) 테스트."""

from __future__ import annotations

import pytest

from quant_agent.config.settings import Settings


def test_defaults_load_without_env():
    """필수 시크릿 없이도 기본값으로 로드된다 (Phase 0)."""
    s = Settings(_env_file=None)
    assert s.duckdb_filename == "quant.duckdb"
    assert s.log_level == "INFO"


def test_duckdb_path_combines_dir_and_filename(tmp_path):
    s = Settings(_env_file=None, data_dir=tmp_path, duckdb_filename="x.duckdb")
    assert s.duckdb_path == tmp_path / "x.duckdb"


def test_require_passes_when_secret_present():
    s = Settings(_env_file=None, discord_webhook_url="https://example.com/hook")
    s.require("discord_webhook_url")  # 예외 없음


def test_require_fails_when_secret_missing():
    """필수 시크릿 누락 시 환경 변수명을 알려주며 실패한다."""
    s = Settings(_env_file=None)
    with pytest.raises(RuntimeError) as exc:
        s.require("discord_webhook_url")
    assert "QA_DISCORD_WEBHOOK_URL" in str(exc.value)


def test_require_fails_on_blank_string():
    s = Settings(_env_file=None, dart_api_key="   ")
    with pytest.raises(RuntimeError, match="QA_DART_API_KEY"):
        s.require("dart_api_key")


def test_require_reports_all_missing():
    s = Settings(_env_file=None)
    with pytest.raises(RuntimeError) as exc:
        s.require("discord_webhook_url", "dart_api_key")
    msg = str(exc.value)
    assert "QA_DISCORD_WEBHOOK_URL" in msg
    assert "QA_DART_API_KEY" in msg


def test_ensure_data_dir_creates(tmp_path):
    target = tmp_path / "nested" / "data"
    s = Settings(_env_file=None, data_dir=target)
    s.ensure_data_dir()
    assert target.exists()
