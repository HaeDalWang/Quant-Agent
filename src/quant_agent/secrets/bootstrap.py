"""시크릿 부트스트랩 — 백엔드 선택 → 환경 주입 → Settings 로드.

관심사 분리: SecretProvider는 "로드"만, 여기서 "주입 + Settings 로드"를 묶는다.
이 한 함수가 로컬(.env)과 클라우드(Secrets Manager)의 유일한 분기점이다.

백엔드 선택은 환경변수 QA_SECRET_BACKEND로 한다(기본 "env"):
- "env": .env/환경변수 그대로 (로컬 기본, 추가 주입 없음)
- "aws": AWS Secrets Manager에서 로드해 환경변수로 주입 (QA_AWS_SECRET_ID 필요)

주입 정책: 이미 설정된 환경변수는 덮어쓰지 않는다(setdefault). 명시적으로 export한
값이 항상 우선하고, 시크릿 백엔드는 비어 있는 키만 채운다 — 디버깅 시 예측 가능.
"""

from __future__ import annotations

import logging
import os

from quant_agent.config.settings import Settings, load_settings
from quant_agent.secrets.aws_provider import AWSSecretsManagerProvider
from quant_agent.secrets.base import SecretError, SecretProvider
from quant_agent.secrets.env_provider import EnvSecretProvider

logger = logging.getLogger(__name__)

_BACKEND_ENV = "QA_SECRET_BACKEND"
_AWS_SECRET_ID_ENV = "QA_AWS_SECRET_ID"
_AWS_REGION_ENV = "QA_AWS_REGION"


def build_provider() -> SecretProvider:
    """QA_SECRET_BACKEND 환경변수에 따라 공급자를 생성한다."""
    backend = os.environ.get(_BACKEND_ENV, "env").strip().lower()

    if backend == "env":
        return EnvSecretProvider()

    if backend == "aws":
        secret_id = os.environ.get(_AWS_SECRET_ID_ENV, "").strip()
        if not secret_id:
            raise SecretError(
                f"{_BACKEND_ENV}=aws 인데 {_AWS_SECRET_ID_ENV}가 설정되지 않았습니다."
            )
        region = os.environ.get(_AWS_REGION_ENV) or None
        return AWSSecretsManagerProvider(secret_id, region=region)

    raise SecretError(f"알 수 없는 시크릿 백엔드: {backend!r} (env|aws 중 하나여야 함)")


def bootstrap_settings() -> Settings:
    """시크릿을 로드·주입하고 Settings를 반환한다.

    진입점(CLI)에서 load_settings() 대신 이 함수를 호출하면 클라우드 시크릿이
    자동 적용된다. 로컬에서는 EnvSecretProvider가 no-op이라 기존 동작과 동일.
    """
    provider = build_provider()
    secrets = provider.load()

    injected = 0
    for key, value in secrets.items():
        if key not in os.environ:  # 명시적 env 우선 (setdefault 의미)
            os.environ[key] = value
            injected += 1

    if injected:
        logger.info(
            "시크릿 %d개를 환경에 주입했습니다 (백엔드=%s).",
            injected,
            os.environ.get(_BACKEND_ENV, "env"),
        )

    return load_settings()
