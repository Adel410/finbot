from pydantic import BaseModel, Field

from .models import MarketData


class Prompt(BaseModel):
    """Provider-independent prompt with separate instruction and input parts."""

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)


class PromptBuilder:
    """Transform market data into provider-neutral prompt parts."""

    def build(self, market: MarketData) -> Prompt:
        return Prompt(
            system_prompt=(
                "Analyze market data and return one structured decision containing "
                "symbol, action, confidence, and a short justification."
            ),
            user_prompt=(
                f"symbol={market.symbol}, previous_close={market.previous_close:.2f}, "
                f"current_price={market.current_price:.2f}, "
                f"one_day_change_percent={market.one_day_change_percent:.4f}, "
                f"five_day_change_percent={market.five_day_change_percent:.4f}, "
                f"last_data_date={market.last_data_date.isoformat()}."
            ),
        )
