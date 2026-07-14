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


settings = Settings()
