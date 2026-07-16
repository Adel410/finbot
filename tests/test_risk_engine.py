from copy import deepcopy
from decimal import Decimal

import pytest

from finbot.models import (
    Action,
    Decision,
    Portfolio,
    Position,
    RiskLimits,
    RiskStatus,
)
from finbot.risk_engine import DuplicateDecisionError, RiskEngine, RiskEngineError

D = Decimal


def decision(symbol: str, action: str, confidence: int = 50) -> Decision:
    return Decision(
        symbol=symbol,
        action=action,
        confidence=confidence,
        justification="Deterministic test decision.",
    )


def engine(**overrides) -> RiskEngine:
    return RiskEngine(RiskLimits(**overrides))


def test_hold_produces_no_action_and_does_not_mutate_portfolio() -> None:
    portfolio = Portfolio(cash=D("1000"))
    before = portfolio.model_dump()

    result = engine().evaluate(portfolio, [decision("AAPL", "HOLD")], {})[0]

    assert result.status == RiskStatus.NO_ACTION
    assert result.quantity == D("0")
    assert result.order_value == D("0")
    assert result.price is None
    assert portfolio.model_dump() == before


def test_standard_buy_is_approved() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("10")},
    )[0]
    assert result.status == RiskStatus.APPROVED
    assert result.quantity == D("10")
    assert result.order_value == D("100")


def test_buy_without_price_is_rejected() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")), [decision("AAPL", "BUY")], {}
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.price is None


@pytest.mark.parametrize("price", [D("0"), D("-1")])
def test_buy_with_non_positive_price_is_rejected(price: Decimal) -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "BUY")],
        {"AAPL": price},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.quantity == D("0")


def test_buy_without_cash_is_rejected() -> None:
    portfolio = Portfolio(
        cash=D("0"),
        positions=[Position(symbol="MSFT", quantity=D("10"), average_price=D("5"))],
    )
    result = engine().evaluate(
        portfolio,
        [decision("AAPL", "BUY")],
        {"AAPL": D("10"), "MSFT": D("10")},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.reason == "No cash is available."


def test_buy_with_zero_portfolio_value_is_rejected() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("0")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("10")},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.reason == "Portfolio value must be positive."


def test_buy_is_rejected_when_maximum_exposure_is_reached() -> None:
    portfolio = Portfolio(
        cash=D("800"),
        positions=[Position(symbol="AAPL", quantity=D("20"), average_price=D("8"))],
    )
    result = engine().evaluate(
        portfolio, [decision("AAPL", "BUY")], {"AAPL": D("10")}
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.reason == "Maximum position exposure already reached."


def test_buy_is_reduced_by_exposure_limit() -> None:
    portfolio = Portfolio(
        cash=D("850"),
        positions=[Position(symbol="AAPL", quantity=D("15"), average_price=D("8"))],
    )
    result = engine().evaluate(
        portfolio, [decision("AAPL", "BUY")], {"AAPL": D("10")}
    )[0]
    assert result.status == RiskStatus.REDUCED
    assert result.quantity == D("5")
    assert result.position_value_after == D("200")
    assert "maximum portfolio exposure" in result.reason


def test_buy_is_reduced_to_available_cash() -> None:
    portfolio = Portfolio(
        cash=D("50"),
        positions=[Position(symbol="MSFT", quantity=D("95"), average_price=D("1"))],
    )
    result = engine(max_position_pct=D("0.50")).evaluate(
        portfolio,
        [decision("AAPL", "BUY")],
        {"AAPL": D("10"), "MSFT": D("10")},
    )[0]
    assert result.status == RiskStatus.REDUCED
    assert result.order_value == D("50")
    assert "available cash" in result.reason


def test_whole_share_rounding_reduces_order_without_rounding_up() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("30")},
    )[0]
    assert result.status == RiskStatus.REDUCED
    assert result.quantity == D("3")
    assert result.order_value == D("90")
    assert "whole-share" in result.reason


def test_buy_rejected_when_one_share_is_too_expensive() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("150")},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.quantity == D("0")


def test_buy_below_minimum_order_value_is_rejected() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("100")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("6")},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert "minimum order value" in result.reason


def test_fractional_buy_is_calculated_with_decimal() -> None:
    result = engine(allow_fractional_shares=True).evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "BUY")],
        {"AAPL": D("40")},
    )[0]
    assert result.status == RiskStatus.APPROVED
    assert result.quantity == D("2.5")
    assert result.order_value == D("100")
    assert isinstance(result.quantity, Decimal)
    assert isinstance(result.order_value, Decimal)


def test_buy_never_exceeds_cash_order_or_position_limits() -> None:
    limits = RiskLimits(max_position_pct=D("0.25"), max_order_pct=D("0.12"))
    portfolio = Portfolio(cash=D("1000"))
    result = RiskEngine(limits).evaluate(
        portfolio, [decision("AAPL", "BUY")], {"AAPL": D("7")}
    )[0]
    assert result.order_value <= portfolio.cash
    assert result.order_value <= result.portfolio_value_before * limits.max_order_pct
    assert result.position_value_after <= result.portfolio_value_before * limits.max_position_pct


def test_sell_full_existing_position_is_approved() -> None:
    position = Position(symbol="AAPL", quantity=D("2.5"), average_price=D("80"))
    result = engine().evaluate(
        Portfolio(cash=D("100"), positions=[position]),
        [decision("AAPL", "SELL")],
        {"AAPL": D("110")},
    )[0]
    assert result.status == RiskStatus.APPROVED
    assert result.quantity == position.quantity
    assert result.order_value == D("275.0")
    assert result.position_value_after == D("0")


def test_sell_unheld_symbol_is_rejected_without_short_position() -> None:
    result = engine().evaluate(
        Portfolio(cash=D("1000")),
        [decision("AAPL", "SELL")],
        {"AAPL": D("10")},
    )[0]
    assert result.status == RiskStatus.REJECTED
    assert result.quantity == D("0")
    assert result.order_value == D("0")
    assert "not currently held" in result.reason


def test_held_position_without_valid_market_price_fails_safe() -> None:
    portfolio = Portfolio(
        cash=D("100"),
        positions=[Position(symbol="AAPL", quantity=D("1"), average_price=D("10"))],
    )
    with pytest.raises(RiskEngineError, match="positive market price"):
        engine().evaluate(portfolio, [decision("AAPL", "SELL")], {})

    with pytest.raises(RiskEngineError, match="positive market price"):
        engine().evaluate(
            portfolio, [decision("AAPL", "SELL")], {"AAPL": D("0")}
        )


def test_duplicate_symbol_decisions_raise_clear_exception() -> None:
    with pytest.raises(DuplicateDecisionError, match="unique symbols"):
        engine().evaluate(
            Portfolio(cash=D("1000")),
            [decision("AAPL", "BUY"), decision("aapl", "SELL")],
            {"AAPL": D("10")},
        )


def test_inputs_are_not_mutated_and_results_keep_input_order() -> None:
    portfolio = Portfolio(cash=D("1000"))
    decisions = [decision("MSFT", "HOLD"), decision("AAPL", "BUY")]
    prices = {"AAPL": D("10")}
    originals = deepcopy((portfolio, decisions, prices))

    results = engine().evaluate(portfolio, decisions, prices)

    assert [result.symbol for result in results] == ["MSFT", "AAPL"]
    assert (portfolio, decisions, prices) == originals


def test_engine_is_deterministic() -> None:
    portfolio = Portfolio(cash=D("1000"))
    decisions = [decision("AAPL", "BUY")]
    prices = {"AAPL": D("10")}
    risk_engine = engine()
    assert risk_engine.evaluate(portfolio, decisions, prices) == risk_engine.evaluate(
        portfolio, decisions, prices
    )


def test_high_ai_confidence_cannot_change_risk_limits() -> None:
    portfolio = Portfolio(cash=D("1000"))
    prices = {"AAPL": D("30")}
    low = engine().evaluate(portfolio, [decision("AAPL", "BUY", 1)], prices)[0]
    high = engine().evaluate(portfolio, [decision("AAPL", "BUY", 100)], prices)[0]
    assert low.model_dump(exclude={"reason"}) == high.model_dump(exclude={"reason"})


def test_portfolio_valuation_uses_market_price_not_average_price() -> None:
    portfolio = Portfolio(
        cash=D("900"),
        positions=[Position(symbol="AAPL", quantity=D("10"), average_price=D("1"))],
    )
    result = engine().evaluate(
        portfolio, [decision("MSFT", "BUY")], {"AAPL": D("10"), "MSFT": D("10")}
    )[0]
    assert result.portfolio_value_before == D("1000")
    assert result.order_value == D("100")


def test_non_decimal_market_price_is_rejected() -> None:
    with pytest.raises(RiskEngineError, match="Decimal"):
        engine().evaluate(
            Portfolio(cash=D("1000")),
            [decision("AAPL", "BUY")],
            {"AAPL": 10},  # type: ignore[dict-item]
        )


def test_successive_buys_cannot_spend_the_same_cash() -> None:
    results = engine(
        max_order_pct=D("1"), max_position_pct=D("1"), min_order_value=D("0")
    ).evaluate(
        Portfolio(cash=D("100")),
        [decision("AAPL", "BUY"), decision("MSFT", "BUY")],
        {"AAPL": D("60"), "MSFT": D("60")},
    )

    assert results[0].order_value == D("60")
    assert results[1].status == RiskStatus.REJECTED
    assert sum(result.order_value for result in results) <= D("100")


def test_sell_then_buy_can_use_released_cash() -> None:
    portfolio = Portfolio(
        cash=D("0"),
        positions=[Position(symbol="AAPL", quantity=D("5"), average_price=D("10"))],
    )
    results = engine(
        max_order_pct=D("1"), max_position_pct=D("1"), min_order_value=D("0")
    ).evaluate(
        portfolio,
        [decision("AAPL", "SELL"), decision("NVDA", "BUY")],
        {"AAPL": D("20"), "NVDA": D("25")},
    )

    assert results[0].order_value == D("100")
    assert results[1].status == RiskStatus.APPROVED
    assert results[1].quantity == D("4")
    assert results[1].order_value == D("100")


def test_many_buys_never_exceed_initial_projected_cash() -> None:
    symbols = ["AAPL", "MSFT", "NVDA", "AMD", "ORCL"]
    results = engine(
        max_order_pct=D("0.30"),
        max_position_pct=D("0.50"),
        min_order_value=D("0"),
    ).evaluate(
        Portfolio(cash=D("1000")),
        [decision(symbol, "BUY") for symbol in symbols],
        {symbol: D("100") for symbol in symbols},
    )

    assert sum(result.order_value for result in results) == D("1000")
    assert results[-1].status == RiskStatus.REJECTED


def test_projected_exposure_stays_within_limit_after_multiple_buys() -> None:
    limits = RiskLimits(
        max_order_pct=D("0.20"),
        max_position_pct=D("0.25"),
        min_order_value=D("0"),
    )
    results = RiskEngine(limits).evaluate(
        Portfolio(cash=D("1000")),
        [decision(symbol, "BUY") for symbol in ["AAPL", "MSFT", "NVDA"]],
        {"AAPL": D("30"), "MSFT": D("40"), "NVDA": D("60")},
    )

    for result in results:
        assert (
            result.position_value_after
            <= result.portfolio_value_before * limits.max_position_pct
        )


def test_batch_projection_does_not_mutate_input_portfolio() -> None:
    portfolio = Portfolio(
        cash=D("100"),
        positions=[Position(symbol="AAPL", quantity=D("2"), average_price=D("15"))],
    )
    before = portfolio.model_dump()

    engine(max_order_pct=D("1"), max_position_pct=D("1")).evaluate(
        portfolio,
        [decision("AAPL", "SELL"), decision("MSFT", "BUY")],
        {"AAPL": D("20"), "MSFT": D("10")},
    )

    assert portfolio.model_dump() == before


def test_batch_projection_is_deterministic() -> None:
    portfolio = Portfolio(cash=D("100"))
    decisions = [decision("AAPL", "BUY"), decision("MSFT", "BUY")]
    prices = {"AAPL": D("60"), "MSFT": D("60")}
    risk_engine = engine(
        max_order_pct=D("1"), max_position_pct=D("1"), min_order_value=D("0")
    )

    assert risk_engine.evaluate(portfolio, decisions, prices) == risk_engine.evaluate(
        portfolio, decisions, prices
    )


def test_reversing_decisions_changes_which_order_uses_scarce_cash() -> None:
    portfolio = Portfolio(cash=D("100"))
    prices = {"AAPL": D("60"), "MSFT": D("70")}
    risk_engine = engine(
        max_order_pct=D("1"), max_position_pct=D("1"), min_order_value=D("0")
    )

    aapl_first = risk_engine.evaluate(
        portfolio,
        [decision("AAPL", "BUY"), decision("MSFT", "BUY")],
        prices,
    )
    msft_first = risk_engine.evaluate(
        portfolio,
        [decision("MSFT", "BUY"), decision("AAPL", "BUY")],
        prices,
    )

    assert [result.symbol for result in aapl_first] == ["AAPL", "MSFT"]
    assert [result.symbol for result in msft_first] == ["MSFT", "AAPL"]
    assert aapl_first[0].order_value == D("60")
    assert msft_first[0].order_value == D("70")
    assert aapl_first[1].status == msft_first[1].status == RiskStatus.REJECTED
