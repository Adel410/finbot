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
