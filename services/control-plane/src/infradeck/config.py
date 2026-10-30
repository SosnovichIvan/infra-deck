"""Validated configuration; secrets never have printable values."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INFRADECK_", env_file=None, hide_input_in_errors=True
    )
    database_url: SecretStr
    origin: str = "http://localhost:5187"
    production: bool = False
    kek_file: Path
    rsa_file: Path
    otp_key_file: Path
    telegram_token: SecretStr
    telegram_username: str
    telegram_webhook_secret: SecretStr
    telegram_proxy: SecretStr = SecretStr("")
    private_cidrs: str = ""

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        origin = urlsplit(self.origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path:
            raise ValueError("Invalid origin")
        proxy = self.telegram_proxy.get_secret_value()
        if proxy:
            value = urlsplit(proxy)
            if (
                value.scheme != "http"
                or not value.hostname
                or not value.port
                or value.username
                or value.password
                or value.path
                or value.query
                or value.fragment
            ):
                raise ValueError("Invalid Telegram proxy configuration")
        if self.production and (origin.scheme != "https" or not proxy):
            raise ValueError("Production requires HTTPS and explicit Telegram proxy")
        if len(self.telegram_webhook_secret.get_secret_value()) < 32:
            raise ValueError("Webhook secret too short")
        return self
