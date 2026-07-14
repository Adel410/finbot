from pathlib import Path
from uuid import uuid4

from config.settings import settings

from .ai_audit import AICallMetrics, AIAuditRecorder
from .ai_provider_contract import AIProvider
from .ai_provider_factory import AIProviderFactory
from .market_data import MarketDataCollector, create_market_data_collector
from .models import PipelineRun
from .prompt_builder import PromptBuilder
from .storage import RunStorage
from .validator import DecisionValidator


def run_pipeline(
    runs_dir: Path = Path("data/runs"),
    collector: MarketDataCollector | None = None,
    audit_recorder: AIAuditRecorder | None = None,
    provider: AIProvider | None = None,
) -> tuple[PipelineRun, Path]:
    collector = collector or create_market_data_collector(settings.market_data_provider)
    prompt_builder = PromptBuilder()
    provider = provider or AIProviderFactory.create(settings)
    validator = DecisionValidator()
    storage = RunStorage(runs_dir)
    audit_recorder = audit_recorder or AIAuditRecorder(settings.usage_dir)
    run_id = uuid4().hex

    market_data = collector.collect()
    prompts = [prompt_builder.build(item) for item in market_data]
    response = provider.analyze_batch(market_data, prompts)
    metrics = getattr(provider, "last_call_metrics", None) or AICallMetrics()
    decisions = [validator.validate(decision) for decision in response.decisions]
    audit_recorder.record(run_id, provider.name, provider.model, prompts, metrics)
    execution = PipelineRun(
        run_id=run_id,
        market_data_provider=collector.name,
        ai_provider=provider.name,
        model=provider.model,
        dry_run=provider.dry_run,
        request_count=metrics.request_count,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        estimated_cost_usd=metrics.estimated_cost_usd,
        actual_cost_usd=metrics.actual_cost_usd,
        duration_seconds=metrics.duration_seconds,
        decisions=decisions,
    )
    return execution, storage.save(execution)
