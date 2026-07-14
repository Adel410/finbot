from .models import MarketData


class PromptBuilder:
    """Transform market data into provider-neutral prompt text."""

    def build(self, market: MarketData) -> str:
        return (
            "Analyze this market data and return a structured decision: "
            f"symbol={market.symbol}, previous_close={market.previous_close:.2f}, "
            f"current_price={market.current_price:.2f}, "
            f"one_day_change_percent={market.one_day_change_percent:.4f}, "
            f"five_day_change_percent={market.five_day_change_percent:.4f}, "
            f"last_data_date={market.last_data_date.isoformat()}."
        )
