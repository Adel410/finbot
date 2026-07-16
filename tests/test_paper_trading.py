from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from finbot.models import (
    Action,
    ExecutionStatus,
    Portfolio,
    Position,
    RiskEvaluation,
    RiskStatus,
    TradeSide,
)
from finbot.paper_trading import PaperTradingEngine

D = Decimal
EXECUTED_AT = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


def evaluation(
    symbol: str,
    action: str,
    status: str,
    quantity: str = "0",
    price: str | None = None,
    order_value: str = "0",
) -> RiskEvaluation:
    decimal_price = D(price) if price is not None else None
    return RiskEvaluation(
        symbol=symbol,
        requested_action=action,
        status=status,
        quantity=D(quantity),
        price=decimal_price,
        order_value=D(order_value),
        reason="Risk evaluation.",
        portfolio_value_before=D("1000"),
        position_value_before=D("0"),
        position_value_after=D(order_value),
    )


def deterministic_engine(*ids: str) -> PaperTradingEngine:
    iterator = iter(ids or ("trade-1", "trade-2", "trade-3"))
    return PaperTradingEngine(
        clock=lambda: EXECUTED_AT,
        trade_id_factory=lambda: next(iterator),
    )


@pytest.mark.parametrize("risk_status", ["NO_ACTION", "REJECTED"])
def test_non_authorized_evaluation_is_skipped(risk_status: str) -> None:
    result = deterministic_engine().execute(
        Portfolio(cash=D("100")),
        [evaluation("AAPL", "HOLD", risk_status)],
    )
    assert result.execution_results[0].execution_status == ExecutionStatus.SKIPPED
    assert result.trades == []
    assert result.updated_portfolio == result.initial_portfolio


def test_simple_buy_updates_cash_and_creates_position_and_trade() -> None:
    result = deterministic_engine("buy-1").execute(
        Portfolio(cash=D("100")),
        [evaluation("aapl", "BUY", "APPROVED", "2", "10", "20")],
    )
    position = result.updated_portfolio.get_position("AAPL")
    assert result.updated_portfolio.cash == D("80")
    assert position is not None
    assert position.quantity == D("2")
    assert position.average_price == D("10")
    assert result.trades[0].side == TradeSide.BUY
    assert result.trades[0].gross_value == D("20")
    assert result.execution_results[0].execution_status == ExecutionStatus.EXECUTED


def test_additional_buy_recalculates_weighted_average() -> None:
    portfolio = Portfolio(
        cash=D("100"),
        positions=[Position(symbol="AAPL", quantity=D("2"), average_price=D("10"))],
    )
    result = deterministic_engine().execute(
        portfolio,
        [evaluation("AAPL", "BUY", "REDUCED", "3", "20", "60")],
    )
    position = result.updated_portfolio.get_position("AAPL")
    assert position is not None
    assert position.quantity == D("5")
    assert position.average_price == D("16")


def test_successive_buys_use_updated_cash() -> None:
    result = deterministic_engine().execute(
        Portfolio(cash=D("100")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "6", "10", "60"),
            evaluation("MSFT", "BUY", "APPROVED", "5", "10", "50"),
        ],
    )
    assert result.execution_results[0].execution_status == ExecutionStatus.EXECUTED
    assert result.execution_results[1].execution_status == ExecutionStatus.FAILED
    assert result.updated_portfolio.cash == D("40")
    assert result.updated_portfolio.get_position("MSFT") is None


def test_failed_buy_does_not_mutate_state_and_next_evaluation_continues() -> None:
    result = deterministic_engine().execute(
        Portfolio(cash=D("30")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "4", "10", "40"),
            evaluation("MSFT", "BUY", "APPROVED", "2", "10", "20"),
        ],
    )
    assert result.execution_results[0].execution_status == ExecutionStatus.FAILED
    assert result.execution_results[1].execution_status == ExecutionStatus.EXECUTED
    assert result.updated_portfolio.cash == D("10")
    assert result.updated_portfolio.get_position("AAPL") is None
    assert result.updated_portfolio.get_position("MSFT") is not None


def test_inconsistent_order_value_fails_without_negative_cash() -> None:
    malformed = RiskEvaluation.model_construct(
        symbol="AAPL",
        requested_action=Action.BUY,
        status=RiskStatus.APPROVED,
        quantity=D("2"),
        price=D("10"),
        order_value=D("19"),
        reason="Malformed.",
        portfolio_value_before=D("100"),
        position_value_before=D("0"),
        position_value_after=D("19"),
    )
    result = deterministic_engine().execute(Portfolio(cash=D("100")), [malformed])
    assert result.execution_results[0].execution_status == ExecutionStatus.FAILED
    assert result.updated_portfolio.cash == D("100")
    assert result.updated_portfolio.cash >= D("0")


@pytest.mark.parametrize(
    ("price", "quantity", "order_value", "reason_fragment"),
    [
        (None, D("1"), D("10"), "positive price"),
        (D("10"), D("0"), D("10"), "positive quantity"),
        (D("10"), D("1"), D("0"), "positive order value"),
    ],
)
def test_malformed_authorized_evaluation_fails_explicitly(
    price, quantity, order_value, reason_fragment
) -> None:
    malformed = RiskEvaluation.model_construct(
        symbol="AAPL",
        requested_action=Action.BUY,
        status=RiskStatus.APPROVED,
        quantity=quantity,
        price=price,
        order_value=order_value,
        reason="Malformed.",
        portfolio_value_before=D("100"),
        position_value_before=D("0"),
        position_value_after=D("0"),
    )
    result = deterministic_engine().execute(Portfolio(cash=D("100")), [malformed])
    execution = result.execution_results[0]
    assert execution.execution_status == ExecutionStatus.FAILED
    assert reason_fragment in execution.reason
    assert result.updated_portfolio.cash == D("100")


def test_full_sale_increases_cash_and_removes_position() -> None:
    portfolio = Portfolio(
        cash=D("10"),
        positions=[Position(symbol="AAPL", quantity=D("3"), average_price=D("8"))],
    )
    result = deterministic_engine("sell-1").execute(
        portfolio,
        [evaluation("AAPL", "SELL", "APPROVED", "3", "12", "36")],
    )
    assert result.updated_portfolio.cash == D("46")
    assert result.updated_portfolio.get_position("AAPL") is None
    assert result.trades[0].side == TradeSide.SELL


def test_partial_sale_preserves_average_price() -> None:
    portfolio = Portfolio(
        cash=D("10"),
        positions=[Position(symbol="AAPL", quantity=D("5"), average_price=D("8"))],
    )
    result = deterministic_engine().execute(
        portfolio,
        [evaluation("AAPL", "SELL", "REDUCED", "2", "12", "24")],
    )
    position = result.updated_portfolio.get_position("AAPL")
    assert position is not None
    assert position.quantity == D("3")
    assert position.average_price == D("8")
    assert result.updated_portfolio.cash == D("34")


@pytest.mark.parametrize(
    ("portfolio", "quantity", "reason_fragment"),
    [
        (Portfolio(cash=D("10")), "1", "without an existing position"),
        (
            Portfolio(
                cash=D("10"),
                positions=[Position(symbol="AAPL", quantity=D("2"), average_price=D("8"))],
            ),
            "3",
            "exceeds the held position",
        ),
    ],
)
def test_invalid_sale_fails_without_creating_short(
    portfolio: Portfolio, quantity: str, reason_fragment: str
) -> None:
    before = portfolio.model_dump()
    result = deterministic_engine().execute(
        portfolio,
        [evaluation("AAPL", "SELL", "APPROVED", quantity, "10", str(D(quantity) * D("10")))],
    )
    execution = result.execution_results[0]
    assert execution.execution_status == ExecutionStatus.FAILED
    assert reason_fragment in execution.reason
    assert result.updated_portfolio.model_dump() == before
    assert all(position.quantity > 0 for position in result.updated_portfolio.positions)


def test_buy_then_sell_same_symbol_is_sequential() -> None:
    result = deterministic_engine("buy", "sell").execute(
        Portfolio(cash=D("100")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "5", "10", "50"),
            evaluation("AAPL", "SELL", "APPROVED", "2", "12", "24"),
        ],
    )
    position = result.updated_portfolio.get_position("AAPL")
    assert position is not None and position.quantity == D("3")
    assert result.updated_portfolio.cash == D("74")
    assert [trade.trade_id for trade in result.trades] == ["buy", "sell"]


def test_sell_then_buy_reuses_released_cash() -> None:
    portfolio = Portfolio(
        cash=D("0"),
        positions=[Position(symbol="AAPL", quantity=D("5"), average_price=D("8"))],
    )
    result = deterministic_engine("sell", "buy").execute(
        portfolio,
        [
            evaluation("AAPL", "SELL", "APPROVED", "5", "10", "50"),
            evaluation("NVDA", "BUY", "APPROVED", "2", "20", "40"),
        ],
    )
    assert result.updated_portfolio.cash == D("10")
    assert result.updated_portfolio.get_position("AAPL") is None
    assert result.updated_portfolio.get_position("NVDA") is not None


def test_order_inputs_and_collections_are_preserved() -> None:
    portfolio = Portfolio(cash=D("100"))
    evaluations = [
        evaluation("MSFT", "HOLD", "NO_ACTION"),
        evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20"),
    ]
    originals = deepcopy((portfolio, evaluations))
    result = deterministic_engine().execute(portfolio, evaluations)
    assert [item.symbol for item in result.execution_results] == ["MSFT", "AAPL"]
    assert [trade.symbol for trade in result.trades] == ["AAPL"]
    assert (portfolio, evaluations) == originals
    assert result.initial_portfolio is not result.updated_portfolio
    assert result.initial_portfolio.positions is not result.updated_portfolio.positions


def test_injected_clock_ids_and_decimal_values_are_used() -> None:
    result = deterministic_engine("custom-id").execute(
        Portfolio(cash=D("100")),
        [evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20")],
    )
    trade = result.trades[0]
    execution = result.execution_results[0]
    assert trade.trade_id == execution.trade_id == "custom-id"
    assert trade.executed_at == EXECUTED_AT
    assert isinstance(trade.quantity, Decimal)
    assert isinstance(trade.price, Decimal)
    assert isinstance(trade.gross_value, Decimal)
    assert isinstance(result.updated_portfolio.cash, Decimal)


def test_identical_injected_dependencies_produce_identical_results() -> None:
    portfolio = Portfolio(cash=D("100"))
    evaluations = [evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20")]
    first = deterministic_engine("same-id").execute(portfolio, evaluations)
    second = deterministic_engine("same-id").execute(portfolio, evaluations)
    assert first == second


def test_clock_is_called_once_per_batch() -> None:
    calls = []

    def clock() -> datetime:
        calls.append(True)
        return EXECUTED_AT

    ids = iter(["one", "two"])
    result = PaperTradingEngine(clock=clock, trade_id_factory=lambda: next(ids)).execute(
        Portfolio(cash=D("100")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20"),
            evaluation("MSFT", "BUY", "APPROVED", "2", "10", "20"),
        ],
    )
    assert len(calls) == 1
    assert {trade.executed_at for trade in result.trades} == {EXECUTED_AT}


def test_naive_clock_is_rejected_before_execution() -> None:
    paper_engine = PaperTradingEngine(
        clock=lambda: datetime(2026, 7, 16, 12, 0),
        trade_id_factory=lambda: "unused",
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        paper_engine.execute(Portfolio(cash=D("100")), [])


def test_duplicate_trade_id_fails_only_the_later_order() -> None:
    result = deterministic_engine("duplicate", "duplicate").execute(
        Portfolio(cash=D("100")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20"),
            evaluation("MSFT", "BUY", "APPROVED", "3", "10", "30"),
        ],
    )

    first, second = result.execution_results
    assert first.execution_status == ExecutionStatus.EXECUTED
    assert second.execution_status == ExecutionStatus.FAILED
    assert second.trade_id is None
    assert second.reason == "Trade identifier is duplicated within this execution batch."
    assert [trade.trade_id for trade in result.trades] == ["duplicate"]
    assert result.updated_portfolio.cash == D("80")
    assert result.updated_portfolio.get_position("AAPL") is not None
    assert result.updated_portfolio.get_position("MSFT") is None


def test_trade_id_factory_failure_is_sanitized_and_batch_continues() -> None:
    calls = 0

    def trade_id_factory() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("sensitive internal detail")
        return "trade-2"

    result = PaperTradingEngine(
        clock=lambda: EXECUTED_AT,
        trade_id_factory=trade_id_factory,
    ).execute(
        Portfolio(cash=D("100")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20"),
            evaluation("MSFT", "BUY", "APPROVED", "3", "10", "30"),
        ],
    )

    first, second = result.execution_results
    assert first.execution_status == ExecutionStatus.FAILED
    assert first.reason == "Trade identifier generation failed."
    assert "sensitive" not in first.reason
    assert second.execution_status == ExecutionStatus.EXECUTED
    assert [trade.trade_id for trade in result.trades] == ["trade-2"]
    assert result.updated_portfolio.cash == D("70")
    assert result.updated_portfolio.get_position("AAPL") is None
    assert result.updated_portfolio.get_position("MSFT") is not None


@pytest.mark.parametrize("invalid_trade_id", ["", "   "])
def test_invalid_trade_id_fails_without_financial_mutation(
    invalid_trade_id: str,
) -> None:
    result = deterministic_engine(invalid_trade_id).execute(
        Portfolio(cash=D("100")),
        [evaluation("AAPL", "BUY", "APPROVED", "2", "10", "20")],
    )
    execution = result.execution_results[0]
    assert execution.execution_status == ExecutionStatus.FAILED
    assert execution.trade_id is None
    assert execution.reason == "Trade identifier is invalid."
    assert result.trades == []
    assert result.updated_portfolio == result.initial_portfolio


def test_trade_id_is_requested_only_after_business_validation() -> None:
    calls = 0

    def trade_id_factory() -> str:
        nonlocal calls
        calls += 1
        return f"trade-{calls}"

    result = PaperTradingEngine(
        clock=lambda: EXECUTED_AT,
        trade_id_factory=trade_id_factory,
    ).execute(
        Portfolio(cash=D("20")),
        [
            evaluation("AAPL", "BUY", "APPROVED", "3", "10", "30"),
            evaluation("MSFT", "BUY", "APPROVED", "1", "10", "10"),
        ],
    )
    assert calls == 1
    assert result.execution_results[0].execution_status == ExecutionStatus.FAILED
    assert result.execution_results[1].trade_id == "trade-1"


def test_engine_never_opens_network_socket(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Network access is forbidden")
        ),
    )
    result = deterministic_engine().execute(
        Portfolio(cash=D("100")),
        [evaluation("AAPL", "BUY", "APPROVED", "1", "10", "10")],
    )
    assert result.execution_results[0].execution_status == ExecutionStatus.EXECUTED
