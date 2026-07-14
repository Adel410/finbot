import importlib

import pytest
from pydantic import ValidationError

from config.settings import Settings
from finbot.market_data import (
    SimulatedMarketDataCollector,
    YFinanceMarketDataCollector,
    create_market_data_collector,
)


def test_simulated_provider_is_default(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    assert Settings().market_data_provider == "simulated"
    assert isinstance(
        create_market_data_collector("simulated"), SimulatedMarketDataCollector
    )


def test_yfinance_provider_can_be_selected(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yfinance")
    assert Settings().market_data_provider == "yfinance"
    assert isinstance(
        create_market_data_collector("yfinance"), YFinanceMarketDataCollector
    )


def test_simulated_ai_provider_is_default(monkeypatch) -> None:
    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "_ENV_FILE", {})
    assert Settings().ai_provider == "simulated"


@pytest.mark.parametrize(
    "overrides",
    [
        {"ai_provider": "grok", "xai_model": "", "xai_dry_run": True},
        {
            "ai_provider": "grok",
            "xai_model": "grok-test",
            "xai_dry_run": False,
            "xai_api_key": "",
        },
        {"ai_provider": "unknown"},
        {"market_data_provider": "unknown"},
        {"max_monthly_api_cost_usd": 0},
    ],
)
def test_invalid_configuration_is_rejected(overrides) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)
