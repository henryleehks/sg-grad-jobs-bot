from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    default_days_back: int = 14
    max_results: int = 20

    @staticmethod
    def from_env() -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        days_back = int(os.getenv("DAYS_BACK", "14"))
        max_results = int(os.getenv("MAX_RESULTS", "20"))
        return Settings(
            telegram_bot_token=token,
            default_days_back=days_back,
            max_results=max_results,
        )
