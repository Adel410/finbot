from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def _uppercase_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol:
        raise ValueError("symbol must not be empty")
    return symbol


class Position(BaseModel):
    """A long-only portfolio position."""

    symbol: str
    quantity: Decimal = Field(gt=0)
    average_price: Decimal = Field(gt=0)

    normalize_symbol = field_validator("symbol", mode="before")(_uppercase_symbol)


class Portfolio(BaseModel):
    cash: Decimal = Field(ge=0)
    positions: list[Position] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_positions(self) -> "Portfolio":
        symbols = [position.symbol for position in self.positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("portfolio positions must have unique symbols")
        return self

    def get_position(self, symbol: str) -> Position | None:
        normalized = _uppercase_symbol(symbol)
        return next(
            (position for position in self.positions if position.symbol == normalized),
            None,
        )

    @property
    def position_symbols(self) -> set[str]:
        return {position.symbol for position in self.positions}


class RiskLimits(BaseModel):
    max_position_pct: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    max_order_pct: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    min_order_value: Decimal = Field(default=Decimal("10"), ge=0)
    allow_fractional_shares: bool = False


class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    REDUCED = "REDUCED"
    REJECTED = "REJECTED"
    NO_ACTION = "NO_ACTION"


class RiskEvaluation(BaseModel):
    symbol: str
    requested_action: Action
    status: RiskStatus
    quantity: Decimal = Field(ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    order_value: Decimal = Field(ge=0)
    reason: str = Field(min_length=1)
    portfolio_value_before: Decimal = Field(ge=0)
    position_value_before: Decimal = Field(ge=0)
    position_value_after: Decimal = Field(ge=0)

    normalize_symbol = field_validator("symbol", mode="before")(_uppercase_symbol)

    @model_validator(mode="after")
    def validate_order_consistency(self) -> "RiskEvaluation":
        if self.status in {RiskStatus.REJECTED, RiskStatus.NO_ACTION}:
            if self.quantity != 0 or self.order_value != 0:
                raise ValueError("rejected and no-action evaluations must have zero size")
        else:
            if self.price is None:
                raise ValueError("approved and reduced evaluations require a price")
            if self.quantity <= 0 or self.order_value <= 0:
                raise ValueError("approved and reduced evaluations require positive size")
        return self


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Trade(BaseModel):
    """Immutable record of a successfully executed virtual transaction."""

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1)
    symbol: str
    side: TradeSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    gross_value: Decimal = Field(gt=0)
    executed_at: datetime

    normalize_symbol = field_validator("symbol", mode="before")(_uppercase_symbol)

    @field_validator("executed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_gross_value(self) -> "Trade":
        if self.gross_value != self.quantity * self.price:
            raise ValueError("gross_value must equal quantity multiplied by price")
        return self


class ExecutionStatus(str, Enum):
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ExecutionResult(BaseModel):
    symbol: str
    requested_action: Action
    risk_status: RiskStatus
    execution_status: ExecutionStatus
    trade_id: str | None = None
    reason: str = Field(min_length=1)
    cash_before: Decimal = Field(ge=0)
    cash_after: Decimal = Field(ge=0)
    position_quantity_before: Decimal = Field(ge=0)
    position_quantity_after: Decimal = Field(ge=0)

    normalize_symbol = field_validator("symbol", mode="before")(_uppercase_symbol)

    @model_validator(mode="after")
    def validate_trade_reference(self) -> "ExecutionResult":
        if self.execution_status == ExecutionStatus.EXECUTED:
            if not self.trade_id:
                raise ValueError("executed results require a trade_id")
        elif self.trade_id is not None:
            raise ValueError("skipped and failed results cannot reference a trade")
        return self


class ExecutionBatchResult(BaseModel):
    initial_portfolio: Portfolio
    updated_portfolio: Portfolio
    trades: list[Trade]
    execution_results: list[ExecutionResult]

    @model_validator(mode="after")
    def validate_execution_order(self) -> "ExecutionBatchResult":
        executed_ids = [
            result.trade_id
            for result in self.execution_results
            if result.execution_status == ExecutionStatus.EXECUTED
        ]
        if executed_ids != [trade.trade_id for trade in self.trades]:
            raise ValueError("trades must match executed results in order")
        if self.initial_portfolio is self.updated_portfolio:
            raise ValueError("initial and updated portfolios must be distinct states")
        return self


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
