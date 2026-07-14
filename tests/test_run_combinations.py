import json
import logging
from types import SimpleNamespace

import pandas as pd
import pytest

from config.settings import Settings
from finbot.ai_audit import AICallMetrics, AIAuditRecorder
from finbot.ai_provider import SimulatedAIProvider
from finbot.ai_provider_contract import AIProvider
from finbot.main import log_active_configuration, log_run_summary
from finbot.market_data import (
    SimulatedMarketDataCollector,
    YFinanceMarketDataCollector,
)
from finbot.models import AIResponse
from finbot.pipeline import run_pipeline


class MockGrokProvider(AIProvider):
    name = "grok"
    model = "grok-mocked"
    dry_run = False

    def __init__(self) -> None:
        self.simulated = SimulatedAIProvider()
        self.last_call_metrics = AICallMetrics(
            request_count=1,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0001,
            actual_cost_usd=0.0002,
            duration_seconds=0.25,
            raw_response='{"safe": true}',
        )

    def analyze(self, market, prompt=None):
        return self.simulated.analyze(market, prompt)

    def analyze_batch(self, markets, prompts):
        return AIResponse(
            decisions=[
                self.analyze(market, prompt)
                for market, prompt in zip(markets, prompts)
            ]
        )


def mocked_yfinance_collector() -> YFinanceMarketDataCollector:
    history = pd.DataFrame(
        {"Close": [100, 101, 102, 103, 104, 105]},
        index=pd.date_range("2026-07-01", periods=6, freq="B"),
    )

    class FakeTicker:
        def history(self, **_kwargs):
            return history

    return YFinanceMarketDataCollector(
        ticker_factory=lambda _symbol: FakeTicker()
    )


@pytest.mark.parametrize(
    ("collector_factory", "provider_factory", "market_name", "ai_name"),
    [
        (
            SimulatedMarketDataCollector,
            SimulatedAIProvider,
            "simulated",
            "simulated",
        ),
        (SimulatedMarketDataCollector, MockGrokProvider, "simulated", "grok"),
        (mocked_yfinance_collector, SimulatedAIProvider, "yfinance", "simulated"),
        (mocked_yfinance_collector, MockGrokProvider, "yfinance", "grok"),
    ],
)
def test_provider_combinations_are_identified_offline(
    tmp_path,
    monkeypatch,
    collector_factory,
    provider_factory,
    market_name,
    ai_name,
) -> None:
    monkeypatch.setattr(
        "socket.socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Network access is forbidden")
        ),
    )
    usage_dir = tmp_path / "usage"

    run, output_path = run_pipeline(
        tmp_path / "runs",
        collector=collector_factory(),
        provider=provider_factory(),
        audit_recorder=AIAuditRecorder(usage_dir),
    )

    stored = json.loads(output_path.read_text(encoding="utf-8"))
    audit = json.loads(next(usage_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert stored["market_data_provider"] == market_name
    assert stored["ai_provider"] == ai_name
    assert audit["run_id"] == stored["run_id"] == run.run_id


def test_logs_and_json_never_contain_secret(tmp_path, caplog) -> None:
    secret = "never-log-this-secret"
    caplog.set_level(logging.INFO)
    active = Settings(
        ai_provider="grok",
        xai_model="grok-mocked",
        xai_dry_run=False,
        xai_api_key=secret,
    )
    log_active_configuration(logging.getLogger("test.config"), active)

    run, output_path = run_pipeline(
        tmp_path / "runs",
        collector=SimulatedMarketDataCollector(),
        provider=MockGrokProvider(),
        audit_recorder=AIAuditRecorder(tmp_path / "usage"),
    )
    log_run_summary(logging.getLogger("test.run"), run, output_path)

    audit_text = next((tmp_path / "usage").glob("*.json")).read_text()
    assert "Market data provider: simulated" in caplog.text
    assert "AI provider: grok" in caplog.text
    assert secret not in caplog.text
    assert secret not in output_path.read_text()
    assert secret not in audit_text
