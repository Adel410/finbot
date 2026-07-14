import logging
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Local settings kept in one place for future configuration needs."""

    runs_dir: Path = Path("data/runs")
    logs_dir: Path = Path("logs")
    log_level: int = logging.INFO
    market_data_provider: Literal["simulated", "yfinance"] = Field(
        default_factory=lambda: os.getenv("MARKET_DATA_PROVIDER", "simulated").lower()
    )
    ai_provider: Literal["simulated", "grok"] = Field(
        default_factory=lambda: os.getenv("AI_PROVIDER", "simulated").lower()
    )
    xai_api_key: str = Field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
    xai_model: str = Field(default_factory=lambda: os.getenv("XAI_MODEL", ""))
    xai_dry_run: bool = Field(
        default_factory=lambda: os.getenv("XAI_DRY_RUN", "true").lower() == "true"
    )
    usage_dir: Path = Path("data/usage")


settings = Settings()
