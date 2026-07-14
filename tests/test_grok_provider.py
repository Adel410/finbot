import json
import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from finbot.grok_provider import (
    GrokBudgetExceededError,
    GrokDryRunError,
    GrokNetworkError,
    GrokResponseError,
    GrokTimeoutError,
    GrokAIProvider,
)
from finbot.models import MarketData
from finbot.prompt_builder import PromptBuilder


def market_and_prompt():
    market = MarketData(
        symbol="AAPL",
        previous_close=100,
        current_price=101,
        one_day_change_percent=1,
        five_day_change_percent=2,
        last_data_date=date(2026, 7, 14),
    )
    return market, PromptBuilder().build(market)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        self.cost_usd = 0.00025


class FakeChat:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.messages = []

    def append(self, message) -> None:
        self.messages.append(message)

    def sample(self):
        if self.error:
            raise self.error
        return self.result


def client_factory_for(chat: FakeChat):
    class FakeClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(create=lambda **_kwargs: chat)

    return lambda **_kwargs: FakeClient()


def provider_for(chat: FakeChat, tmp_path: Path) -> GrokAIProvider:
    return GrokAIProvider(
        model="grok-4.5",
        api_key="test-secret",
        dry_run=False,
        usage_dir=tmp_path,
        client_factory=client_factory_for(chat),
    )


def valid_content() -> str:
    return json.dumps(
        {
            "decisions": [
                {
                    "symbol": "AAPL",
                    "action": "BUY",
                    "confidence": 80,
                    "justification": "Positive daily momentum.",
                }
            ]
        }
    )


def test_success_parses_and_validates_response(tmp_path) -> None:
    market, prompt = market_and_prompt()
    provider = provider_for(FakeChat(FakeResponse(valid_content())), tmp_path)

    result = provider.analyze_batch([market], [prompt])

    assert result.decisions[0].action.value == "BUY"
    assert provider.last_call_metrics.input_tokens == 100
    assert provider.last_call_metrics.output_tokens == 20
    assert provider.last_call_metrics.actual_cost_usd == 0.00025


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConnectionError("offline"), GrokNetworkError),
        (TimeoutError(), GrokTimeoutError),
    ],
)
def test_transport_errors_are_explicit(tmp_path, error, expected) -> None:
    market, prompt = market_and_prompt()
    provider = provider_for(FakeChat(error=error), tmp_path)

    with pytest.raises(expected):
        provider.analyze_batch([market], [prompt])


def test_invalid_json_is_rejected(tmp_path) -> None:
    market, prompt = market_and_prompt()
    provider = provider_for(FakeChat(FakeResponse("not-json")), tmp_path)

    with pytest.raises(GrokResponseError, match="invalid structured JSON"):
        provider.analyze_batch([market], [prompt])


def test_budget_exceeded_prevents_client_creation(tmp_path) -> None:
    audit = {
        "created_at": "2026-07-14T00:00:00Z",
        "actual_cost_usd": 5.0,
    }
    (tmp_path / "ai_audit_existing.json").write_text(json.dumps(audit))
    market, prompt = market_and_prompt()
    provider = provider_for(FakeChat(FakeResponse(valid_content())), tmp_path)
    provider.budget.spent_usd = lambda: 5.0

    with pytest.raises(GrokBudgetExceededError):
        provider.analyze_batch([market], [prompt])


def test_dry_run_never_creates_client(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    market, prompt = market_and_prompt()

    def forbidden_client(**_kwargs):
        raise AssertionError("Client must not be created")

    provider = GrokAIProvider(
        model="grok-4.5",
        api_key="test-secret",
        dry_run=True,
        usage_dir=tmp_path,
        client_factory=forbidden_client,
    )

    with pytest.raises(GrokDryRunError, match="no API request was sent"):
        provider.analyze_batch([market], [prompt])
    assert "dry-run mode" in caplog.text
