"""One proxy-configured Bot API transport for enrollment and OTP delivery."""

import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.methods.base import TelegramMethod, TelegramType
from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError

from infradeck.config import Settings
from infradeck.errors import Rejected


class TelegramSession(AiohttpSession):
    async def make_request(
        self, bot: Bot, method: TelegramMethod[TelegramType], timeout: int | None = None
    ) -> TelegramType:
        try:
            return await super().make_request(bot, method, timeout)
        except (ProxyConnectionError, ProxyTimeoutError, ProxyError):
            raise TelegramNetworkError(
                method=method, message="Telegram proxy unavailable"
            ) from None


class Telegram:
    def __init__(self, settings: Settings, api: TelegramAPIServer | None = None):
        self.api = api
        self.token = settings.telegram_token.get_secret_value()
        self.proxy = settings.telegram_proxy.get_secret_value() or None

    async def _send(self, chat_id: int, text: str) -> None:
        session = (
            TelegramSession(proxy=self.proxy, timeout=10, api=self.api)
            if self.api
            else TelegramSession(proxy=self.proxy, timeout=10)
        )
        try:
            async with Bot(self.token, session=session) as bot:
                await bot.send_message(chat_id, text, protect_content=True)
        except (TelegramAPIError, OSError, TimeoutError):
            raise Rejected("Telegram недоступен. Повторите отправку позже", 503) from None

    def send(self, chat_id: int, text: str) -> None:
        asyncio.run(self._send(chat_id, text))
