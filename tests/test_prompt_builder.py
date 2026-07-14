from datetime import date

from finbot.models import MarketData
from finbot.prompt_builder import PromptBuilder


def test_prompt_builder_contains_all_market_values() -> None:
    market = MarketData(
        symbol="AAPL",
        previous_close=225.0,
        current_price=230.4,
        one_day_change_percent=2.4,
        five_day_change_percent=3.2,
        last_data_date=date(2026, 7, 13),
    )

    prompt = PromptBuilder().build(market)

    assert prompt.system_prompt
    assert "AAPL" in prompt.user_prompt
    assert "225.00" in prompt.user_prompt
    assert "230.40" in prompt.user_prompt
    assert "2.4000" in prompt.user_prompt
    assert "3.2000" in prompt.user_prompt
    assert "2026-07-13" in prompt.user_prompt
