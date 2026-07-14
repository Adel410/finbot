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


class PipelineRun(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decisions: list[Decision] = Field(min_length=1)
