import logging
import math
from abc import ABC, abstractmethod
from datetime import date
from typing import Callable

from .models import MarketData

logger = logging.getLogger(__name__)

SYMBOLS = ("AAPL", "MSFT", "NVDA")


class MarketDataCollectionError(RuntimeError):
    """Base error for an explicit market-data collection failure."""


class UnknownSymbolError(MarketDataCollectionError):
    pass


class EmptyHistoryError(MarketDataCollectionError):
    pass


class MissingDataError(MarketDataCollectionError):
    pass


class InvalidMarketValueError(MarketDataCollectionError):
    pass


class MarketDataNetworkError(MarketDataCollectionError):
    pass


class MarketDataCollector(ABC):
    """Contract implemented by every market-data source."""

    @abstractmethod
    def collect(self) -> list[MarketData]:
        raise NotImplementedError


class SimulatedMarketDataCollector(MarketDataCollector):
    """Collect deterministic local data for tests and offline development."""

    def collect(self) -> list[MarketData]:
        return load_market_data()


class YFinanceMarketDataCollector(MarketDataCollector):
    """Collect daily closing prices from yfinance."""

    def __init__(
        self,
        symbols: tuple[str, ...] = SYMBOLS,
        ticker_factory: Callable | None = None,
    ) -> None:
        if ticker_factory is None:
            import yfinance as yf

            ticker_factory = yf.Ticker
        self.symbols = symbols
        self.ticker_factory = ticker_factory

    def collect(self) -> list[MarketData]:
        return [self._collect_symbol(symbol) for symbol in self.symbols]

    def _collect_symbol(self, symbol: str) -> MarketData:
        try:
            history = self.ticker_factory(symbol).history(
                period="1mo", interval="1d", auto_adjust=False, raise_errors=True
            )
            return market_data_from_history(symbol, history)
        except MarketDataCollectionError:
            logger.exception("Market data collection failed for %s", symbol)
            raise
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name in {"YFTzMissingError", "YFPricesMissingError"}:
                error = UnknownSymbolError(f"Unknown symbol: {symbol}")
            else:
                error = MarketDataNetworkError(
                    f"Unable to retrieve market data for {symbol}: {exc}"
                )
            logger.exception("Market data collection failed for %s", symbol)
            raise error from exc


def market_data_from_history(symbol: str, history) -> MarketData:
    """Validate closing history and calculate one- and five-session changes."""
    if history is None or history.empty:
        raise EmptyHistoryError(f"Empty history for {symbol}")
    if "Close" not in history.columns:
        raise MissingDataError(f"Missing Close data for {symbol}")

    closes = history["Close"]
    if closes.isna().any():
        raise MissingDataError(f"Missing closing value for {symbol}")
    if len(closes) < 6:
        raise MissingDataError(f"At least six daily closes are required for {symbol}")

    try:
        values = [float(value) for value in closes.iloc[-6:]]
    except (TypeError, ValueError) as exc:
        raise InvalidMarketValueError(f"Non-numeric closing value for {symbol}") from exc
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise InvalidMarketValueError(f"Invalid closing value for {symbol}")

    current_price = values[-1]
    previous_close = values[-2]
    one_day_change = (current_price - previous_close) / previous_close * 100
    five_day_change = (current_price - values[0]) / values[0] * 100

    last_index = closes.index[-1]
    try:
        last_data_date = last_index.date()
    except AttributeError as exc:
        raise MissingDataError(f"Missing last data date for {symbol}") from exc
    if not isinstance(last_data_date, date):
        raise MissingDataError(f"Invalid last data date for {symbol}")

    return MarketData(
        symbol=symbol,
        previous_close=previous_close,
        current_price=current_price,
        one_day_change_percent=one_day_change,
        five_day_change_percent=five_day_change,
        last_data_date=last_data_date,
    )


def create_market_data_collector(provider: str) -> MarketDataCollector:
    if provider == "simulated":
        return SimulatedMarketDataCollector()
    if provider == "yfinance":
        return YFinanceMarketDataCollector()
    raise ValueError(f"Unsupported market data provider: {provider}")


def load_market_data() -> list[MarketData]:
    """Return the original fixed data with stable simulated decisions."""
    return [
        MarketData(
            symbol="AAPL",
            previous_close=225.00,
            current_price=230.40,
            one_day_change_percent=2.4,
            five_day_change_percent=2.4,
            last_data_date=date(2026, 1, 5),
        ),
        MarketData(
            symbol="MSFT",
            previous_close=450.00,
            current_price=439.20,
            one_day_change_percent=-2.4,
            five_day_change_percent=-2.4,
            last_data_date=date(2026, 1, 5),
        ),
        MarketData(
            symbol="NVDA",
            previous_close=135.00,
            current_price=135.40,
            one_day_change_percent=(135.40 - 135.00) / 135.00 * 100,
            five_day_change_percent=(135.40 - 135.00) / 135.00 * 100,
            last_data_date=date(2026, 1, 5),
        ),
    ]
