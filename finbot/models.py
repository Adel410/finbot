from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketData(BaseModel):
    symbol: str = Field(min_length=1)
    previous_close: float = Field(gt=0)
    current_price: float = Field(gt=0)
    one_day_change_percent: float
    five_day_change_percent: float
    last_data_date: date


class Decision(BaseModel):
    symbol: str = Field(min_length=1)
    action: Action
    confidence: int = Field(ge=0, le=100)
    justification: str = Field(min_length=1, max_length=160)


class AIResponse(BaseModel):
    """Provider-independent structured AI response."""

    decisions: list[Decision] = Field(min_length=1)


class PipelineRun(BaseModel):
    run_id: str = Field(min_length=32, max_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    market_data_provider: str = Field(min_length=1)
    ai_provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    dry_run: bool
    request_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)
    market_data: list[MarketData] = Field(min_length=1)
    decisions: list[Decision] = Field(min_length=1)
