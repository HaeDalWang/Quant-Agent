"""AWS Secrets Manager 기반 시크릿 공급자 (클라우드).

GitHub Actions·Lambda·EC2 등 클라우드 배포 시 사용한다. Secrets Manager에
JSON 형태로 저장된 시크릿({"QA_KIS_APP_KEY": "...", ...})을 읽어 dict로 반환한다.

boto3는 메서드 내부에서 lazy import한다 — AWS를 쓰지 않는 로컬 환경에서는
boto3 미설치 상태로도 이 모듈 import가 깨지지 않게 하기 위함이다. AWS를 쓰려면
`uv sync --extra aws`로 boto3를 설치한다.

자격증명은 boto3 기본 체인(환경변수·~/.aws·IAM 역할)을 따른다 — 코드에 키를
넣지 않는다.
"""

from __future__ import annotations

import json

from quant_agent.secrets.base import SecretError, SecretProvider


class AWSSecretsManagerProvider(SecretProvider):
    """AWS Secrets Manager에서 JSON 시크릿을 로드하는 공급자."""

    def __init__(self, secret_id: str, region: str | None = None) -> None:
        if not secret_id or not secret_id.strip():
            raise ValueError("secret_id가 비어 있습니다.")
        self._secret_id = secret_id
        self._region = region

    def load(self) -> dict[str, str]:
        client = self._build_client()
        try:
            resp = client.get_secret_value(SecretId=self._secret_id)
        except Exception as exc:  # boto3 ClientError 등을 도메인 예외로 변환
            raise SecretError(f"Secrets Manager 접근 실패: {self._secret_id}: {exc}") from exc

        raw = resp.get("SecretString")
        if raw is None:
            raise SecretError(
                f"시크릿에 SecretString이 없습니다(바이너리 미지원): {self._secret_id}"
            )

        return self._parse(raw)

    def _build_client(self):
        """boto3 클라이언트를 생성한다 (lazy import)."""
        try:
            import boto3  # noqa: PLC0415  (optional 의존성 lazy import)
        except ImportError as exc:
            raise SecretError(
                "AWS Secrets Manager를 쓰려면 boto3가 필요합니다: uv sync --extra aws"
            ) from exc

        kwargs = {"service_name": "secretsmanager"}
        if self._region:
            kwargs["region_name"] = self._region
        return boto3.client(**kwargs)

    def _parse(self, raw: str) -> dict[str, str]:
        """JSON 시크릿을 문자열 dict로 파싱한다."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SecretError(f"시크릿이 유효한 JSON이 아닙니다: {self._secret_id}: {exc}") from exc

        if not isinstance(data, dict):
            raise SecretError(f"시크릿 JSON은 객체여야 합니다(키-값): {self._secret_id}")

        # 모든 값을 문자열로 정규화 (환경변수 주입 대상)
        return {str(k): str(v) for k, v in data.items()}
