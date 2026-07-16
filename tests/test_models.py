import pytest
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import ValidationError

from finbot.models import (
    Decision,
    ExecutionBatchResult,
    ExecutionResult,
    Portfolio,
    Position,
    RiskEvaluation,
    RiskLimits,
    Trade,
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


def test_trade_is_valid_immutable_and_normalizes_symbol() -> None:
    trade = Trade(
        trade_id="trade-1",
        symbol=" aapl ",
        side="BUY",
        quantity=Decimal("2"),
        price=Decimal("10"),
        gross_value=Decimal("20"),
        executed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert trade.symbol == "AAPL"
    with pytest.raises(ValidationError):
        trade.quantity = Decimal("3")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", Decimal("0")),
        ("price", Decimal("0")),
        ("gross_value", Decimal("19")),
        ("executed_at", datetime(2026, 1, 1)),
    ],
)
def test_trade_rejects_invalid_values(field: str, value: object) -> None:
    payload = {
        "trade_id": "trade-1",
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": Decimal("2"),
        "price": Decimal("10"),
        "gross_value": Decimal("20"),
        "executed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        Trade(**payload)


def execution_result_payload() -> dict:
    return {
        "symbol": "AAPL",
        "requested_action": "BUY",
        "risk_status": "APPROVED",
        "execution_status": "EXECUTED",
        "trade_id": "trade-1",
        "reason": "Executed.",
        "cash_before": Decimal("100"),
        "cash_after": Decimal("80"),
        "position_quantity_before": Decimal("0"),
        "position_quantity_after": Decimal("2"),
    }


def test_executed_result_requires_trade_id() -> None:
    payload = execution_result_payload()
    payload["trade_id"] = None
    with pytest.raises(ValidationError, match="require a trade_id"):
        ExecutionResult(**payload)


def test_skipped_result_cannot_reference_trade() -> None:
    payload = execution_result_payload()
    payload["execution_status"] = "SKIPPED"
    with pytest.raises(ValidationError, match="cannot reference"):
        ExecutionResult(**payload)


def test_execution_batch_is_coherent() -> None:
    trade = Trade(
        trade_id="trade-1",
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("2"),
        price=Decimal("10"),
        gross_value=Decimal("20"),
        executed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    result = ExecutionResult(**execution_result_payload())
    batch = ExecutionBatchResult(
        initial_portfolio=Portfolio(cash=Decimal("100")),
        updated_portfolio=Portfolio(
            cash=Decimal("80"),
            positions=[Position(symbol="AAPL", quantity=Decimal("2"), average_price=Decimal("10"))],
        ),
        trades=[trade],
        execution_results=[result],
    )
    assert batch.trades[0].trade_id == batch.execution_results[0].trade_id
