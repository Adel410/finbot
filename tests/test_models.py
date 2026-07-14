import pytest
from pydantic import ValidationError

from finbot.models import Decision


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

