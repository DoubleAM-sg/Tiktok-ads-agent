"""Environment-backed settings for the TikTok Ads Agent."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All secrets + runtime config, loaded from env or .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tiktok_app_id: str = Field(..., description="TikTok developer app ID")
    tiktok_app_secret: str = Field(..., description="TikTok developer app secret")
    tiktok_access_token: str = Field(..., description="Long-lived access token")
    tiktok_advertiser_id: str = Field(..., description="Advertiser ID to operate on")
    tiktok_bc_id: str = Field(default="", description="Business Center ID (optional)")
    tiktok_sandbox: bool = Field(default=False, description="Use sandbox API host")

    telegram_bot_token: str = Field(..., description="Telegram bot API token")
    telegram_chat_id: str = Field(..., description="Telegram chat/supergroup ID")
    telegram_topic_id: str = Field(
        default="", description="Telegram supergroup topic ID (optional)"
    )

    @property
    def tiktok_base_url(self) -> str:
        if self.tiktok_sandbox:
            return "https://sandbox-ads.tiktok.com/open_api/v1.3"
        return "https://business-api.tiktok.com/open_api/v1.3"


def load_settings() -> Settings:
    """Load a validated Settings instance from the environment."""

    return Settings()  # type: ignore[call-arg]
