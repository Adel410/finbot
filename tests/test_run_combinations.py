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


def test_collected_data_is_the_data_prompted_sent_and_stored(tmp_path) -> None:
    collector = SimulatedMarketDataCollector()
    collected = collector.collect()

    class FixedCollector(SimulatedMarketDataCollector):
        def collect(self):
            return collected

    class CapturingProvider(MockGrokProvider):
        def analyze_batch(self, markets, prompts):
            self.received_markets = markets
            self.received_prompts = prompts
            return super().analyze_batch(markets, prompts)

    provider = CapturingProvider()
    run, output_path = run_pipeline(
        tmp_path / "runs",
        collector=FixedCollector(),
        provider=provider,
        audit_recorder=AIAuditRecorder(tmp_path / "usage"),
    )

    stored = json.loads(output_path.read_text(encoding="utf-8"))
    assert provider.received_markets is collected
    assert run.market_data == collected == provider.received_markets
    assert stored["market_data"] == [item.model_dump(mode="json") for item in collected]
    for market, prompt in zip(provider.received_markets, provider.received_prompts):
        assert market.symbol in prompt.user_prompt
        assert f"current_price={market.current_price:.2f}" in prompt.user_prompt
        assert market.last_data_date.isoformat() in prompt.user_prompt


def test_mocked_yfinance_snapshot_preserves_values_and_date(tmp_path) -> None:
    run, output_path = run_pipeline(
        tmp_path / "runs",
        collector=mocked_yfinance_collector(),
        provider=SimulatedAIProvider(),
        audit_recorder=AIAuditRecorder(tmp_path / "usage"),
    )

    first = run.market_data[0]
    stored = json.loads(output_path.read_text(encoding="utf-8"))["market_data"][0]
    assert first.previous_close == 104
    assert first.current_price == 105
    assert first.one_day_change_percent == pytest.approx((105 - 104) / 104 * 100)
    assert first.five_day_change_percent == pytest.approx(5.0)
    assert first.last_data_date.isoformat() == "2026-07-08"
    assert stored == first.model_dump(mode="json")


def test_failed_provider_call_has_sanitized_audit(tmp_path) -> None:
    secret = "must-not-be-audited"

    class FailingProvider(MockGrokProvider):
        def analyze_batch(self, markets, prompts):
            self.last_call_metrics = AICallMetrics(request_count=1)
            raise RuntimeError(secret)

    usage_dir = tmp_path / "usage"
    with pytest.raises(RuntimeError, match=secret):
        run_pipeline(
            tmp_path / "runs",
            collector=SimulatedMarketDataCollector(),
            provider=FailingProvider(),
            audit_recorder=AIAuditRecorder(usage_dir),
        )

    audit_text = next(usage_dir.glob("*.json")).read_text(encoding="utf-8")
    audit = json.loads(audit_text)
    assert audit["success"] is False
    assert audit["error_type"] == "RuntimeError"
    assert audit["message"] == "AI provider call failed"
    assert audit["request_count"] == 1
    assert secret not in audit_text
