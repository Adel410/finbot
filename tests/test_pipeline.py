import json

from finbot.ai_provider import SimulatedAIProvider
from finbot.pipeline import run_pipeline
from finbot.market_data import SimulatedMarketDataCollector


def test_pipeline_writes_a_valid_json_run(tmp_path) -> None:
    execution, output_path = run_pipeline(
        tmp_path / "runs",
        collector=SimulatedMarketDataCollector(),
        provider=SimulatedAIProvider(),
    )

    assert output_path.exists()
    stored = json.loads(output_path.read_text(encoding="utf-8"))
    expected_metadata = {
        "run_id",
        "created_at",
        "market_data_provider",
        "ai_provider",
        "model",
        "dry_run",
        "request_count",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "duration_seconds",
        "decisions",
    }
    assert expected_metadata <= stored.keys()
    assert stored["market_data_provider"] == "simulated"
    assert stored["ai_provider"] == "simulated"
    assert stored["model"] == "deterministic-local"
    assert stored["request_count"] == 0
    assert stored["input_tokens"] == 0
    assert stored["output_tokens"] == 0
    assert stored["estimated_cost_usd"] == 0.0
    assert stored["actual_cost_usd"] is None
    assert stored["duration_seconds"] == 0.0
    assert len(execution.decisions) == 3
    assert [item.action.value for item in execution.decisions] == [
        "BUY",
        "SELL",
        "HOLD",
    ]
    assert [item.confidence for item in execution.decisions] == [84, 84, 62]
    assert [item["symbol"] for item in stored["decisions"]] == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]
