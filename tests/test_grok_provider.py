from datetime import date

import pytest

from finbot.grok_provider import GrokAIProvider
from finbot.models import MarketData
from finbot.prompt_builder import PromptBuilder


def test_grok_provider_cannot_execute() -> None:
    market = MarketData(
        symbol="AAPL",
        previous_close=100,
        current_price=101,
        one_day_change_percent=1,
        five_day_change_percent=2,
        last_data_date=date(2026, 7, 14),
    )

    with pytest.raises(NotImplementedError, match="no request was sent"):
        GrokAIProvider().analyze(market, PromptBuilder().build(market))

