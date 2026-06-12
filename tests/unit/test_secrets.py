"""시크릿 공급자 및 부트스트랩 테스트 (네트워크/boto3 없이 모킹).

boto3는 optional 의존성이라 설치돼 있지 않을 수 있다. AWS 공급자는 _build_client를
가짜 클라이언트로 패치해 JSON 파싱·에러 경로만 검증한다(boto3 실제 호출 없음).
"""

from __future__ import annotations

import pytest

from quant_agent.secrets.aws_provider import AWSSecretsManagerProvider
from quant_agent.secrets.base import SecretError
from quant_agent.secrets.bootstrap import bootstrap_settings, build_provider
from quant_agent.secrets.env_provider import EnvSecretProvider

# --- EnvSecretProvider ---


def test_env_provider_returns_empty():
    """Env 공급자는 추가 주입이 없어 빈 dict (Settings가 .env 직접 로드)."""
    assert EnvSecretProvider().load() == {}


# --- AWSSecretsManagerProvider ---


class _FakeClient:
    def __init__(self, secret_string: str | None) -> None:
        self._secret_string = secret_string
        self.requested_id: str | None = None

    def get_secret_value(self, SecretId: str):  # noqa: N803 (boto3 API 시그니처)
        self.requested_id = SecretId
        if self._secret_string is None:
            return {}
        return {"SecretString": self._secret_string}


def _provider_with(monkeypatch, secret_string, secret_id="quant/prod"):
    provider = AWSSecretsManagerProvider(secret_id, region="ap-northeast-2")
    fake = _FakeClient(secret_string)
    monkeypatch.setattr(provider, "_build_client", lambda: fake)
    return provider, fake


def test_aws_rejects_empty_secret_id():
    with pytest.raises(ValueError, match="비어 있습니다"):
        AWSSecretsManagerProvider("")


def test_aws_parses_json_secret(monkeypatch):
    provider, fake = _provider_with(
        monkeypatch, '{"QA_KIS_APP_KEY": "abc", "QA_KIS_APP_SECRET": "xyz"}'
    )
    result = provider.load()
    assert result == {"QA_KIS_APP_KEY": "abc", "QA_KIS_APP_SECRET": "xyz"}
    assert fake.requested_id == "quant/prod"


def test_aws_coerces_values_to_str(monkeypatch):
    """JSON 숫자·불리언도 환경변수 주입을 위해 문자열로 정규화."""
    provider, _ = _provider_with(monkeypatch, '{"QA_PORT": 8080, "QA_FLAG": true}')
    result = provider.load()
    assert result == {"QA_PORT": "8080", "QA_FLAG": "True"}


def test_aws_raises_on_invalid_json(monkeypatch):
    provider, _ = _provider_with(monkeypatch, "not-json{{{")
    with pytest.raises(SecretError, match="유효한 JSON이 아닙니다"):
        provider.load()


def test_aws_raises_on_non_object_json(monkeypatch):
    provider, _ = _provider_with(monkeypatch, '["a", "b"]')
    with pytest.raises(SecretError, match="객체여야 합니다"):
        provider.load()


def test_aws_raises_when_no_secret_string(monkeypatch):
    provider, _ = _provider_with(monkeypatch, None)
    with pytest.raises(SecretError, match="SecretString이 없습니다"):
        provider.load()


def test_aws_wraps_client_error(monkeypatch):
    provider = AWSSecretsManagerProvider("quant/prod")

    class _Boom:
        def get_secret_value(self, SecretId):  # noqa: N803
            raise RuntimeError("AccessDenied")

    monkeypatch.setattr(provider, "_build_client", lambda: _Boom())
    with pytest.raises(SecretError, match="Secrets Manager 접근 실패"):
        provider.load()


# --- bootstrap.build_provider ---


def test_build_provider_defaults_to_env(monkeypatch):
    monkeypatch.delenv("QA_SECRET_BACKEND", raising=False)
    assert isinstance(build_provider(), EnvSecretProvider)


def test_build_provider_env_explicit(monkeypatch):
    monkeypatch.setenv("QA_SECRET_BACKEND", "env")
    assert isinstance(build_provider(), EnvSecretProvider)


def test_build_provider_aws(monkeypatch):
    monkeypatch.setenv("QA_SECRET_BACKEND", "aws")
    monkeypatch.setenv("QA_AWS_SECRET_ID", "quant/prod")
    provider = build_provider()
    assert isinstance(provider, AWSSecretsManagerProvider)


def test_build_provider_aws_missing_secret_id(monkeypatch):
    monkeypatch.setenv("QA_SECRET_BACKEND", "aws")
    monkeypatch.delenv("QA_AWS_SECRET_ID", raising=False)
    with pytest.raises(SecretError, match="QA_AWS_SECRET_ID"):
        build_provider()


def test_build_provider_unknown_backend(monkeypatch):
    monkeypatch.setenv("QA_SECRET_BACKEND", "vault")
    with pytest.raises(SecretError, match="알 수 없는 시크릿 백엔드"):
        build_provider()


# --- bootstrap_settings 주입 정책 ---


def test_bootstrap_injects_into_env(monkeypatch, tmp_path):
    """aws 백엔드 시크릿이 환경변수로 주입되고 Settings에 반영된다."""
    monkeypatch.setenv("QA_SECRET_BACKEND", "aws")
    monkeypatch.setenv("QA_AWS_SECRET_ID", "quant/prod")
    monkeypatch.setenv("QA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QA_KIS_APP_KEY", raising=False)

    # build_provider가 만든 AWS 공급자의 load를 모킹
    import quant_agent.secrets.bootstrap as boot

    class _FakeProvider:
        def load(self):
            return {"QA_KIS_APP_KEY": "injected-key"}

    monkeypatch.setattr(boot, "build_provider", lambda: _FakeProvider())

    settings = bootstrap_settings()
    assert settings.kis_app_key == "injected-key"


def test_bootstrap_respects_existing_env(monkeypatch, tmp_path):
    """명시적으로 설정된 환경변수는 시크릿이 덮어쓰지 않는다 (setdefault)."""
    monkeypatch.setenv("QA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("QA_KIS_APP_KEY", "explicit-key")

    import quant_agent.secrets.bootstrap as boot

    class _FakeProvider:
        def load(self):
            return {"QA_KIS_APP_KEY": "from-secrets"}

    monkeypatch.setattr(boot, "build_provider", lambda: _FakeProvider())

    settings = bootstrap_settings()
    # 명시적 env가 이김
    assert settings.kis_app_key == "explicit-key"
