"""애플리케이션 설정 및 시작 시 검증.

시크릿·환경설정을 `.env`에서 로드하고, 필수 값이 없으면 시작 단계에서
명확히 실패한다(fail-fast). 비기능 요구사항: "시크릿 누락 시 시작 단계에서 명확히 실패한다."
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 (이 파일 기준 src/quant_agent/config/settings.py → 3단계 상위)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    """환경 변수 기반 설정.

    Phase 0에서는 외부 시크릿이 필수는 아니지만(무료 공개 데이터로 시작),
    선택적 시크릿을 미리 선언해 둔다. Phase 1+ 에서 알림/공시 연동 시 활성화한다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="QA_",
        extra="ignore",
    )

    # --- 저장소 ---
    data_dir: Path = Field(default=DEFAULT_DATA_DIR, description="DuckDB·캐시 저장 디렉토리")
    duckdb_filename: str = Field(default="quant.duckdb", description="DuckDB 파일명")

    # --- 선택적 시크릿 (Phase 1+) ---
    discord_webhook_url: str | None = Field(
        default=None, description="알림용 Discord webhook URL (Phase 1)"
    )
    dart_api_key: str | None = Field(
        default=None, description="국내 공시(DART) OpenAPI 키 (Phase 1)"
    )

    # --- 운영 ---
    log_level: str = Field(default="INFO", description="로깅 레벨")

    @property
    def duckdb_path(self) -> Path:
        """DuckDB 파일 전체 경로."""
        return self.data_dir / self.duckdb_filename

    def ensure_data_dir(self) -> None:
        """데이터 디렉토리를 생성한다 (없으면)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def require(self, *fields: str) -> None:
        """지정한 시크릿 필드가 모두 설정됐는지 검증한다.

        Phase별로 필요한 시크릿이 다르므로, 진입점에서 필요한 것만 명시적으로
        요구한다. 누락 시 어떤 환경 변수를 채워야 하는지 명확히 알려준다.

        Raises:
            RuntimeError: 필수 필드가 None이거나 빈 값일 때.
        """
        missing = []
        for field in fields:
            value = getattr(self, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                env_name = f"{self.model_config['env_prefix']}{field.upper()}"
                missing.append(env_name)
        if missing:
            raise RuntimeError(
                "필수 환경 변수가 설정되지 않았습니다: "
                + ", ".join(missing)
                + " — .env 파일을 확인하세요."
            )


def load_settings() -> Settings:
    """설정을 로드하고 데이터 디렉토리를 준비한다."""
    settings = Settings()
    settings.ensure_data_dir()
    return settings
