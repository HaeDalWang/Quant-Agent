"""환경변수/.env 기반 시크릿 공급자 (로컬 기본).

로컬 개발의 기본 백엔드. pydantic-settings의 Settings가 이미 .env와 환경변수를
직접 읽으므로, 이 공급자는 추가로 주입할 것이 없어 빈 dict를 반환한다(no-op).

존재 이유: bootstrap이 항상 SecretProvider를 거치게 해서, 로컬→클라우드 전환이
"공급자 교체" 한 줄로 끝나도록 한다. 로컬에서도 같은 코드 경로를 탄다.
"""

from __future__ import annotations

from quant_agent.secrets.base import SecretProvider


class EnvSecretProvider(SecretProvider):
    """환경변수/.env 패스스루 공급자.

    Settings가 .env를 직접 로드하므로 여기서는 아무것도 주입하지 않는다.
    """

    def load(self) -> dict[str, str]:
        return {}
