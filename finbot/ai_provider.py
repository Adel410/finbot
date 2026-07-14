from .models import Action, Decision, MarketData


class SimulatedAIProvider:
    """Deterministic provider designed to be replaced by a real provider later."""

    def analyze(self, market: MarketData) -> Decision:
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

