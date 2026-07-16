import pytest
from decimal import Decimal
from pydantic import ValidationError

from finbot.models import (
    Decision,
    Portfolio,
    Position,
    RiskEvaluation,
    RiskLimits,
)


@pytest.mark.parametrize("action", ["BUY", "SELL", "HOLD"])
def test_allowed_actions(action: str) -> None:
    decision = Decision(
        symbol="AAPL", action=action, confidence=50, justification="Valid reason."
    )
    assert decision.action.value == action


@pytest.mark.parametrize(
    ("field", "value"),
    [("action", "WAIT"), ("confidence", -1), ("confidence", 101)],
)
def test_invalid_decision_is_rejected(field: str, value: object) -> None:
    payload = {
        "symbol": "AAPL",
        "action": "HOLD",
        "confidence": 50,
        "justification": "Valid reason.",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        Decision(**payload)


def test_position_is_valid_and_symbol_is_normalized() -> None:
    position = Position(symbol=" aapl ", quantity=Decimal("2.5"), average_price=Decimal("100"))
    assert position.symbol == "AAPL"
    assert position.quantity == Decimal("2.5")


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", Decimal("0")), ("average_price", Decimal("0"))],
)
def test_position_rejects_non_positive_values(field: str, value: Decimal) -> None:
    payload = {
        "symbol": "AAPL",
        "quantity": Decimal("1"),
        "average_price": Decimal("100"),
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        Position(**payload)


def test_portfolio_rejects_negative_cash() -> None:
    with pytest.raises(ValidationError):
        Portfolio(cash=Decimal("-0.01"))


def test_portfolio_rejects_duplicate_normalized_symbols() -> None:
    with pytest.raises(ValidationError, match="unique symbols"):
        Portfolio(
            cash=Decimal("100"),
            positions=[
                Position(symbol="AAPL", quantity=Decimal("1"), average_price=Decimal("10")),
                Position(symbol="aapl", quantity=Decimal("2"), average_price=Decimal("11")),
            ],
        )


def test_portfolio_position_helpers() -> None:
    position = Position(symbol="AAPL", quantity=Decimal("1"), average_price=Decimal("10"))
    portfolio = Portfolio(cash=Decimal("100"), positions=[position])
    assert portfolio.get_position("aapl") == position
    assert portfolio.position_symbols == {"AAPL"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_position_pct", Decimal("0")),
        ("max_position_pct", Decimal("1.01")),
        ("max_order_pct", Decimal("0")),
        ("max_order_pct", Decimal("1.01")),
        ("min_order_value", Decimal("-1")),
    ],
)
def test_risk_limits_reject_invalid_values(field: str, value: Decimal) -> None:
    with pytest.raises(ValidationError):
        RiskLimits(**{field: value})


def test_risk_limit_defaults_are_explicit_decimals() -> None:
    limits = RiskLimits()
    assert limits.max_position_pct == Decimal("0.20")
    assert limits.max_order_pct == Decimal("0.10")
    assert limits.min_order_value == Decimal("10")
    assert limits.allow_fractional_shares is False


def test_rejected_evaluation_must_have_zero_size() -> None:
    with pytest.raises(ValidationError, match="zero size"):
        RiskEvaluation(
            symbol="AAPL",
            requested_action="BUY",
            status="REJECTED",
            quantity=Decimal("1"),
            price=Decimal("10"),
            order_value=Decimal("10"),
            reason="Rejected.",
            portfolio_value_before=Decimal("100"),
            position_value_before=Decimal("0"),
            position_value_after=Decimal("0"),
        )


def test_approved_evaluation_requires_positive_price() -> None:
    with pytest.raises(ValidationError):
        RiskEvaluation(
            symbol="AAPL",
            requested_action="BUY",
            status="APPROVED",
            quantity=Decimal("1"),
            price=None,
            order_value=Decimal("10"),
            reason="Approved.",
            portfolio_value_before=Decimal("100"),
            position_value_before=Decimal("0"),
            position_value_after=Decimal("10"),
        )


def test_approved_evaluation_requires_positive_size() -> None:
    with pytest.raises(ValidationError, match="positive size"):
        RiskEvaluation(
            symbol="AAPL",
            requested_action="BUY",
            status="APPROVED",
            quantity=Decimal("0"),
            price=Decimal("10"),
            order_value=Decimal("0"),
            reason="Approved.",
            portfolio_value_before=Decimal("100"),
            position_value_before=Decimal("0"),
            position_value_after=Decimal("0"),
        )
