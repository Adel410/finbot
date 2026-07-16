from decimal import Decimal, ROUND_FLOOR

from .models import (
    Action,
    Decision,
    Portfolio,
    Position,
    RiskEvaluation,
    RiskLimits,
    RiskStatus,
)

ZERO = Decimal("0")


class RiskEngineError(ValueError):
    """Raised when safe portfolio valuation is impossible."""


class DuplicateDecisionError(RiskEngineError):
    """Raised when one evaluation contains conflicting symbol decisions."""


class RiskEngine:
    """Deterministically authorize and size long-only proposed orders."""

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate(
        self,
        portfolio: Portfolio,
        decisions: list[Decision],
        market_prices: dict[str, Decimal],
    ) -> list[RiskEvaluation]:
        prices = self._normalize_prices(market_prices)
        self._validate_unique_decisions(decisions)
        portfolio_value = self._portfolio_value(portfolio, prices)

        return [
            self._evaluate_decision(portfolio, decision, prices, portfolio_value)
            for decision in decisions
        ]

    @staticmethod
    def _normalize_prices(prices: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized: dict[str, Decimal] = {}
        for symbol, price in prices.items():
            if not isinstance(price, Decimal):
                raise RiskEngineError("market prices must use Decimal")
            normalized_symbol = symbol.strip().upper()
            if not normalized_symbol:
                raise RiskEngineError("market price symbol must not be empty")
            normalized[normalized_symbol] = price
        return normalized

    @staticmethod
    def _validate_unique_decisions(decisions: list[Decision]) -> None:
        symbols = [decision.symbol.strip().upper() for decision in decisions]
        if len(symbols) != len(set(symbols)):
            raise DuplicateDecisionError("decisions must have unique symbols")

    @staticmethod
    def _portfolio_value(
        portfolio: Portfolio, prices: dict[str, Decimal]
    ) -> Decimal:
        total = portfolio.cash
        for position in portfolio.positions:
            price = prices.get(position.symbol)
            if price is None or price <= ZERO:
                raise RiskEngineError(
                    f"A positive market price is required for held position {position.symbol}"
                )
            total += position.quantity * price
        return total

    def _evaluate_decision(
        self,
        portfolio: Portfolio,
        decision: Decision,
        prices: dict[str, Decimal],
        portfolio_value: Decimal,
    ) -> RiskEvaluation:
        symbol = decision.symbol.strip().upper()
        position = portfolio.get_position(symbol)
        price = prices.get(symbol)
        position_value = position.quantity * price if position and price else ZERO

        if decision.action == Action.HOLD:
            safe_price = price if price is not None and price > ZERO else None
            return self._no_order(
                symbol,
                decision.action,
                RiskStatus.NO_ACTION,
                safe_price,
                "AI decision is HOLD; no order generated.",
                portfolio_value,
                position_value,
            )
        if decision.action == Action.SELL:
            return self._evaluate_sell(
                symbol, position, price, portfolio_value, position_value
            )
        return self._evaluate_buy(
            symbol, portfolio, position, price, portfolio_value, position_value
        )

    def _evaluate_buy(
        self,
        symbol: str,
        portfolio: Portfolio,
        position: Position | None,
        price: Decimal | None,
        portfolio_value: Decimal,
        position_value: Decimal,
    ) -> RiskEvaluation:
        if price is None:
            return self._rejected(
                symbol,
                Action.BUY,
                None,
                "Market price is missing.",
                portfolio_value,
                position_value,
            )
        if price <= ZERO:
            return self._rejected(
                symbol,
                Action.BUY,
                None,
                "Market price must be positive.",
                portfolio_value,
                position_value,
            )
        if portfolio_value <= ZERO:
            return self._rejected(
                symbol,
                Action.BUY,
                price,
                "Portfolio value must be positive.",
                portfolio_value,
                position_value,
            )
        if portfolio.cash == ZERO:
            return self._rejected(
                symbol,
                Action.BUY,
                price,
                "No cash is available.",
                portfolio_value,
                position_value,
            )

        max_order_value = portfolio_value * self.limits.max_order_pct
        max_position_value = portfolio_value * self.limits.max_position_pct
        remaining_capacity = max_position_value - position_value
        if remaining_capacity <= ZERO:
            return self._rejected(
                symbol,
                Action.BUY,
                price,
                "Maximum position exposure already reached.",
                portfolio_value,
                position_value,
            )

        allowed_value = min(max_order_value, remaining_capacity, portfolio.cash)
        constrained_by = None
        if remaining_capacity < max_order_value and remaining_capacity <= portfolio.cash:
            constrained_by = "exposure"
        elif portfolio.cash < max_order_value and portfolio.cash < remaining_capacity:
            constrained_by = "cash"

        raw_quantity = allowed_value / price
        quantity = (
            raw_quantity
            if self.limits.allow_fractional_shares
            else raw_quantity.to_integral_value(rounding=ROUND_FLOOR)
        )
        order_value = quantity * price
        if quantity <= ZERO:
            return self._rejected(
                symbol,
                Action.BUY,
                price,
                "Capital is insufficient to buy the minimum share quantity.",
                portfolio_value,
                position_value,
            )
        if order_value < self.limits.min_order_value:
            return self._rejected(
                symbol,
                Action.BUY,
                price,
                "Order value is below the minimum order value.",
                portfolio_value,
                position_value,
            )

        if constrained_by == "exposure":
            status = RiskStatus.REDUCED
            reason = "Buy size reduced because the symbol is close to its maximum portfolio exposure."
        elif constrained_by == "cash":
            status = RiskStatus.REDUCED
            reason = "Buy size reduced to available cash."
        elif not self.limits.allow_fractional_shares and order_value < max_order_value:
            status = RiskStatus.REDUCED
            reason = "Buy size reduced to a whole-share quantity."
        else:
            status = RiskStatus.APPROVED
            reason = "Buy approved within order and exposure limits."

        return RiskEvaluation(
            symbol=symbol,
            requested_action=Action.BUY,
            status=status,
            quantity=quantity,
            price=price,
            order_value=order_value,
            reason=reason,
            portfolio_value_before=portfolio_value,
            position_value_before=position_value,
            position_value_after=position_value + order_value,
        )

    def _evaluate_sell(
        self,
        symbol: str,
        position: Position | None,
        price: Decimal | None,
        portfolio_value: Decimal,
        position_value: Decimal,
    ) -> RiskEvaluation:
        if position is None:
            return self._rejected(
                symbol,
                Action.SELL,
                price if price is not None and price > ZERO else None,
                "Cannot sell a symbol that is not currently held.",
                portfolio_value,
                ZERO,
            )
        if price is None or price <= ZERO:
            return self._rejected(
                symbol,
                Action.SELL,
                None,
                "A positive market price is required to sell.",
                portfolio_value,
                position_value,
            )
        order_value = position.quantity * price
        return RiskEvaluation(
            symbol=symbol,
            requested_action=Action.SELL,
            status=RiskStatus.APPROVED,
            quantity=position.quantity,
            price=price,
            order_value=order_value,
            reason="Full position sale approved.",
            portfolio_value_before=portfolio_value,
            position_value_before=order_value,
            position_value_after=ZERO,
        )

    def _rejected(
        self,
        symbol: str,
        action: Action,
        price: Decimal | None,
        reason: str,
        portfolio_value: Decimal,
        position_value: Decimal,
    ) -> RiskEvaluation:
        return self._no_order(
            symbol,
            action,
            RiskStatus.REJECTED,
            price,
            reason,
            portfolio_value,
            position_value,
        )

    @staticmethod
    def _no_order(
        symbol: str,
        action: Action,
        status: RiskStatus,
        price: Decimal | None,
        reason: str,
        portfolio_value: Decimal,
        position_value: Decimal,
    ) -> RiskEvaluation:
        return RiskEvaluation(
            symbol=symbol,
            requested_action=action,
            status=status,
            quantity=ZERO,
            price=price,
            order_value=ZERO,
            reason=reason,
            portfolio_value_before=portfolio_value,
            position_value_before=position_value,
            position_value_after=position_value,
        )
