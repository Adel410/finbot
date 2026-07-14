from .ai_provider_contract import AIProvider
from .models import AIResponse, Action, Decision, MarketData
from .prompt_builder import Prompt


class SimulatedAIProvider(AIProvider):
    """Deterministic provider designed to be replaced by a real provider later."""

    name = "simulated"
    model = "deterministic-local"
    dry_run = False

    def analyze(self, market: MarketData, prompt: Prompt | None = None) -> Decision:
        change_percent = (
            (market.current_price - market.previous_close) / market.previous_close * 100
        )

        if change_percent >= 1:
            action = Action.BUY
            justification = "Positive simulated momentum above 1%."
        elif change_percent <= -1:
            action = Action.SELL
            justification = "Negative simulated momentum below -1%."
        else:
            action = Action.HOLD
            justification = "Simulated price movement remains within 1%."

        confidence = min(100, 60 + int(abs(change_percent) * 10))
        return Decision(
            symbol=market.symbol,
            action=action,
            confidence=confidence,
            justification=justification,
        )

    def analyze_batch(
        self, markets: list[MarketData], prompts: list[Prompt]
    ) -> AIResponse:
        return AIResponse(
            decisions=[
                self.analyze(market, prompt)
                for market, prompt in zip(markets, prompts)
            ]
        )
