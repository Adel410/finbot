from finbot.ai_provider import SimulatedAIProvider
from finbot.market_data import SimulatedMarketDataCollector


def test_provider_is_deterministic_and_returns_expected_actions() -> None:
    provider = SimulatedAIProvider()
    market_data = SimulatedMarketDataCollector().collect()

    first = [provider.analyze(item) for item in market_data]
    second = [provider.analyze(item) for item in market_data]

    assert first == second
    assert [decision.action.value for decision in first] == ["BUY", "SELL", "HOLD"]
