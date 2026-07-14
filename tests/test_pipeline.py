import json

from finbot.pipeline import run_pipeline
from finbot.market_data import SimulatedMarketDataCollector


def test_pipeline_writes_a_valid_json_run(tmp_path) -> None:
    execution, output_path = run_pipeline(
        tmp_path / "runs", collector=SimulatedMarketDataCollector()
    )

    assert output_path.exists()
    stored = json.loads(output_path.read_text(encoding="utf-8"))
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
