"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot-wide configuration sourced from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "ledger_bot"

    # Chat IDs
    in_chat_id: int = -1001852638516
    out_chat_id: int = -1001816909345
    report_chat_id: int = -1003746938542

    # Timezone & accounting period
    timezone: str = "Asia/Kathmandu"
    day_cutover_hour: int = 20  # 8 PM

    # Logging
    log_level: str = "INFO"


# Singleton – import this from anywhere
settings = Settings()  # type: ignore[call-arg]
