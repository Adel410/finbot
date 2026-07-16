from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError

from .models import (
    Action,
    ExecutionBatchResult,
    ExecutionResult,
    ExecutionStatus,
    Portfolio,
    Position,
    RiskEvaluation,
    RiskStatus,
    Trade,
    TradeSide,
)

ZERO = Decimal("0")
AUTHORIZED_STATUSES = {RiskStatus.APPROVED, RiskStatus.REDUCED}


@dataclass
class _ExecutionState:
    cash: Decimal
    positions: dict[str, Position]

    @classmethod
    def from_portfolio(cls, portfolio: Portfolio) -> "_ExecutionState":
        return cls(
            cash=portfolio.cash,
            positions={
                position.symbol: position.model_copy(deep=True)
                for position in portfolio.positions
            },
        )

    def quantity(self, symbol: str) -> Decimal:
        position = self.positions.get(symbol)
        return position.quantity if position else ZERO

    def to_portfolio(self) -> Portfolio:
        return Portfolio(
            cash=self.cash,
            positions=[position.model_copy(deep=True) for position in self.positions.values()],
        )


class PaperTradingEngine:
    """Sequentially apply risk-authorized orders to an isolated virtual state.

    The clock is called once per batch, so all successful trades in that batch
    share one timezone-aware execution timestamp.
    """

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        trade_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.trade_id_factory = trade_id_factory or (lambda: uuid4().hex)

    def execute(
        self,
        portfolio: Portfolio,
        evaluations: list[RiskEvaluation],
    ) -> ExecutionBatchResult:
        executed_at = self.clock()
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ValueError("paper-trading clock must return a timezone-aware datetime")

        initial = portfolio.model_copy(deep=True)
        state = _ExecutionState.from_portfolio(portfolio)
        trades: list[Trade] = []
        results: list[ExecutionResult] = []

        for evaluation in evaluations:
            result, trade = self._execute_evaluation(state, evaluation, executed_at)
            results.append(result)
            if trade is not None:
                trades.append(trade)

        return ExecutionBatchResult(
            initial_portfolio=initial,
            updated_portfolio=state.to_portfolio(),
            trades=trades,
            execution_results=results,
        )

    def _execute_evaluation(
        self,
        state: _ExecutionState,
        evaluation: RiskEvaluation,
        executed_at: datetime,
    ) -> tuple[ExecutionResult, Trade | None]:
        symbol = evaluation.symbol
        cash_before = state.cash
        quantity_before = state.quantity(symbol)

        if evaluation.status not in AUTHORIZED_STATUSES:
            return (
                self._result(
                    evaluation,
                    ExecutionStatus.SKIPPED,
                    None,
                    "Risk evaluation does not authorize an order.",
                    cash_before,
                    cash_before,
                    quantity_before,
                    quantity_before,
                ),
                None,
            )

        inconsistency = self._validate_authorized_evaluation(evaluation)
        if inconsistency:
            return self._failed(
                evaluation, inconsistency, cash_before, quantity_before
            )

        if evaluation.requested_action == Action.BUY:
            return self._execute_buy(state, evaluation, executed_at)
        if evaluation.requested_action == Action.SELL:
            return self._execute_sell(state, evaluation, executed_at)
        return self._failed(
            evaluation,
            "An authorized HOLD evaluation cannot be executed.",
            cash_before,
            quantity_before,
        )

    @staticmethod
    def _validate_authorized_evaluation(evaluation: RiskEvaluation) -> str | None:
        if evaluation.price is None or evaluation.price <= ZERO:
            return "Execution requires a positive price."
        if evaluation.quantity <= ZERO:
            return "Execution requires a positive quantity."
        if evaluation.order_value <= ZERO:
            return "Execution requires a positive order value."
        if evaluation.order_value != evaluation.quantity * evaluation.price:
            return "Order value does not equal quantity multiplied by price."
        return None

    def _execute_buy(
        self,
        state: _ExecutionState,
        evaluation: RiskEvaluation,
        executed_at: datetime,
    ) -> tuple[ExecutionResult, Trade | None]:
        cash_before = state.cash
        quantity_before = state.quantity(evaluation.symbol)
        if evaluation.order_value > cash_before:
            return self._failed(
                evaluation,
                "Insufficient cash to execute buy.",
                cash_before,
                quantity_before,
            )

        trade = self._build_trade(evaluation, TradeSide.BUY, executed_at)
        if trade is None:
            return self._failed(
                evaluation,
                "Trade identifier is invalid.",
                cash_before,
                quantity_before,
            )

        existing = state.positions.get(evaluation.symbol)
        new_quantity = quantity_before + evaluation.quantity
        if existing is None:
            average_price = evaluation.price
        else:
            average_price = (
                existing.quantity * existing.average_price
                + evaluation.quantity * evaluation.price
            ) / new_quantity

        state.cash = cash_before - evaluation.order_value
        state.positions[evaluation.symbol] = Position(
            symbol=evaluation.symbol,
            quantity=new_quantity,
            average_price=average_price,
        )
        return (
            self._result(
                evaluation,
                ExecutionStatus.EXECUTED,
                trade.trade_id,
                "Virtual buy executed.",
                cash_before,
                state.cash,
                quantity_before,
                new_quantity,
            ),
            trade,
        )

    def _execute_sell(
        self,
        state: _ExecutionState,
        evaluation: RiskEvaluation,
        executed_at: datetime,
    ) -> tuple[ExecutionResult, Trade | None]:
        cash_before = state.cash
        existing = state.positions.get(evaluation.symbol)
        quantity_before = existing.quantity if existing else ZERO
        if existing is None:
            return self._failed(
                evaluation,
                "Cannot execute sale without an existing position.",
                cash_before,
                quantity_before,
            )
        if evaluation.quantity > quantity_before:
            return self._failed(
                evaluation,
                "Sale quantity exceeds the held position.",
                cash_before,
                quantity_before,
            )

        trade = self._build_trade(evaluation, TradeSide.SELL, executed_at)
        if trade is None:
            return self._failed(
                evaluation,
                "Trade identifier is invalid.",
                cash_before,
                quantity_before,
            )

        remaining = quantity_before - evaluation.quantity
        state.cash = cash_before + evaluation.order_value
        if remaining == ZERO:
            state.positions.pop(evaluation.symbol)
        else:
            state.positions[evaluation.symbol] = Position(
                symbol=evaluation.symbol,
                quantity=remaining,
                average_price=existing.average_price,
            )
        return (
            self._result(
                evaluation,
                ExecutionStatus.EXECUTED,
                trade.trade_id,
                "Virtual sale executed.",
                cash_before,
                state.cash,
                quantity_before,
                remaining,
            ),
            trade,
        )

    def _build_trade(
        self,
        evaluation: RiskEvaluation,
        side: TradeSide,
        executed_at: datetime,
    ) -> Trade | None:
        try:
            return Trade(
                trade_id=self.trade_id_factory(),
                symbol=evaluation.symbol,
                side=side,
                quantity=evaluation.quantity,
                price=evaluation.price,
                gross_value=evaluation.order_value,
                executed_at=executed_at,
            )
        except ValidationError:
            return None

    @staticmethod
    def _failed(
        evaluation: RiskEvaluation,
        reason: str,
        cash: Decimal,
        quantity: Decimal,
    ) -> tuple[ExecutionResult, None]:
        return (
            PaperTradingEngine._result(
                evaluation,
                ExecutionStatus.FAILED,
                None,
                reason,
                cash,
                cash,
                quantity,
                quantity,
            ),
            None,
        )

    @staticmethod
    def _result(
        evaluation: RiskEvaluation,
        status: ExecutionStatus,
        trade_id: str | None,
        reason: str,
        cash_before: Decimal,
        cash_after: Decimal,
        quantity_before: Decimal,
        quantity_after: Decimal,
    ) -> ExecutionResult:
        return ExecutionResult(
            symbol=evaluation.symbol,
            requested_action=evaluation.requested_action,
            risk_status=evaluation.status,
            execution_status=status,
            trade_id=trade_id,
            reason=reason,
            cash_before=cash_before,
            cash_after=cash_after,
            position_quantity_before=quantity_before,
            position_quantity_after=quantity_after,
        )
