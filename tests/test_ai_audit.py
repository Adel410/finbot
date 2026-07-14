import json

from finbot.ai_audit import AIAuditRecorder
from finbot.market_data import SimulatedMarketDataCollector
from finbot.pipeline import run_pipeline


def test_simulated_pipeline_has_zero_ai_usage_and_needs_no_network(
    tmp_path, monkeypatch
) -> None:
    def block_network(*_args, **_kwargs):
        raise AssertionError("Network access is forbidden")

    monkeypatch.setattr("socket.socket", block_network)
    usage_dir = tmp_path / "usage"

    run_pipeline(
        tmp_path / "runs",
        collector=SimulatedMarketDataCollector(),
        audit_recorder=AIAuditRecorder(usage_dir),
    )

    audit_file = next(usage_dir.glob("*.json"))
    audit = json.loads(audit_file.read_text(encoding="utf-8"))
    assert audit["provider"] == "simulated"
    assert audit["model"] == "deterministic-local"
    assert len(audit["prompts"]) == 3
    assert audit["request_count"] == 0
    assert audit["input_tokens"] == 0
    assert audit["output_tokens"] == 0
    assert audit["cost"] == 0.0
