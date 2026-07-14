import logging
import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr, model_validator


_ENV_FILE = dotenv_values(Path(".env"))


def _env_file_value(name: str, default: str = "") -> str:
    value = _ENV_FILE.get(name, default)
    return value if isinstance(value, str) else default


class Settings(BaseModel):
    """Local settings kept in one place for future configuration needs."""

    runs_dir: Path = Path("data/runs")
    logs_dir: Path = Path("logs")
    log_level: int = logging.INFO
    market_data_provider: Literal["simulated", "yfinance"] = Field(
        default_factory=lambda: os.getenv("MARKET_DATA_PROVIDER", "simulated").lower()
    )
    ai_provider: Literal["simulated", "grok"] = Field(
        default_factory=lambda: _env_file_value("AI_PROVIDER", "simulated").lower()
    )
    xai_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(_env_file_value("XAI_API_KEY"))
    )
    xai_model: str = Field(default_factory=lambda: _env_file_value("XAI_MODEL"))
    xai_dry_run: bool = Field(
        default_factory=lambda: _env_file_value("XAI_DRY_RUN", "true").lower()
        == "true"
    )
    max_monthly_api_cost_usd: float = Field(
        default_factory=lambda: float(
            _env_file_value("MAX_MONTHLY_API_COST_USD", "5.00")
        ),
        gt=0,
    )
    usage_dir: Path = Path("data/usage")

    @model_validator(mode="after")
    def validate_ai_configuration(self) -> "Settings":
        if self.ai_provider == "grok" and not self.xai_model:
            raise ValueError("XAI_MODEL is required when AI_PROVIDER=grok")
        if (
            self.ai_provider == "grok"
            and not self.xai_dry_run
            and not self.xai_api_key.get_secret_value()
        ):
            raise ValueError(
                "XAI_API_KEY is required when Grok dry-run mode is disabled"
            )
        return self


settings = Settings()
