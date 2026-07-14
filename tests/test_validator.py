from finbot.models import Decision
from finbot.validator import DecisionValidator


def test_validator_returns_a_validated_copy() -> None:
    decision = Decision(
        symbol="AAPL",
        action="BUY",
        confidence=84,
        justification="Positive simulated momentum above 1%.",
    )

    validated = DecisionValidator().validate(decision)

    assert validated == decision
    assert validated is not decision
