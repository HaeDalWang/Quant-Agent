"""알림 채널 팩토리 — 설정에 따라 적절한 채널을 선택한다.

webhook URL이 설정돼 있으면 Discord, 없으면 Console로 폴백한다. 이 폴백 덕분에
개발·CI 환경(webhook 없음)에서도 안전하게 동작하고, 운영에서는 .env에 URL만
넣으면 Discord로 전환된다 — 코드 변경 없이.
"""

from __future__ import annotations

import logging

from quant_agent.alerts.base import AlertChannel
from quant_agent.alerts.console import ConsoleChannel
from quant_agent.alerts.discord import DiscordChannel
from quant_agent.config.settings import Settings

logger = logging.getLogger(__name__)


def build_channel(settings: Settings) -> AlertChannel:
    """설정 기반으로 알림 채널을 생성한다.

    webhook URL이 있으면 DiscordChannel, 없으면 ConsoleChannel.
    """
    url = settings.discord_webhook_url
    if url and url.strip():
        logger.debug("Discord 채널 사용")
        return DiscordChannel(url)
    logger.info("Discord webhook 미설정 — 콘솔 채널로 폴백")
    return ConsoleChannel()
