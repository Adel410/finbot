from datetime import datetime

import pandas as pd
import pytest

from finbot.market_data import (
    EmptyHistoryError,
    InvalidMarketValueError,
    MarketDataNetworkError,
    MissingDataError,
    UnknownSymbolError,
    YFinanceMarketDataCollector,
    market_data_from_history,
)


def history_with_closes(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": values},
        index=pd.date_range(datetime(2026, 7, 1), periods=len(values), freq="B"),
    )


def test_calculates_one_day_change() -> None:
    result = market_data_from_history(
        "AAPL", history_with_closes([100, 101, 102, 103, 104, 106])
    )

    assert result.one_day_change_percent == pytest.approx((106 - 104) / 104 * 100)


def test_calculates_five_day_change() -> None:
    result = market_data_from_history(
        "AAPL", history_with_closes([100, 101, 102, 103, 104, 110])
    )

    assert result.five_day_change_percent == pytest.approx(10.0)


@pytest.mark.parametrize(
    "history",
    [pd.DataFrame(), pd.DataFrame({"Open": [1, 2, 3, 4, 5, 6]})],
)
def test_rejects_empty_or_missing_history(history: pd.DataFrame) -> None:
    expected_error = EmptyHistoryError if history.empty else MissingDataError
    with pytest.raises(expected_error):
        market_data_from_history("AAPL", history)


def test_yfinance_collector_uses_mocked_history() -> None:
    history = history_with_closes([100, 101, 102, 103, 104, 106])

    class FakeTicker:
        def history(self, **kwargs):
            assert kwargs["interval"] == "1d"
            return history

    collector = YFinanceMarketDataCollector(
        symbols=("AAPL",), ticker_factory=lambda _symbol: FakeTicker()
    )

    assert collector.collect()[0].current_price == 106


def test_rejects_non_numeric_close() -> None:
    history = history_with_closes([100, 101, 102, 103, 104, 106])
    history["Close"] = history["Close"].astype(object)
    history.iloc[-1, 0] = "invalid"

    with pytest.raises(InvalidMarketValueError):
        market_data_from_history("AAPL", history)


def test_maps_unknown_symbol_error() -> None:
    class YFTzMissingError(Exception):
        pass

    class FakeTicker:
        def history(self, **_kwargs):
            raise YFTzMissingError("no timezone")

    collector = YFinanceMarketDataCollector(
        symbols=("UNKNOWN",), ticker_factory=lambda _symbol: FakeTicker()
    )

    with pytest.raises(UnknownSymbolError):
        collector.collect()


def test_maps_network_error() -> None:
    class FakeTicker:
        def history(self, **_kwargs):
            raise ConnectionError("offline")

    collector = YFinanceMarketDataCollector(
        symbols=("AAPL",), ticker_factory=lambda _symbol: FakeTicker()
    )

    with pytest.raises(MarketDataNetworkError):
        collector.collect()
