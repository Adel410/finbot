from pathlib import Path

from config.settings import settings

from .ai_audit import AIAuditRecorder
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
) -> tuple[PipelineRun, Path]:
    collector = collector or create_market_data_collector(settings.market_data_provider)
    prompt_builder = PromptBuilder()
    provider = AIProviderFactory.create(settings)
    validator = DecisionValidator()
    storage = RunStorage(runs_dir)
    audit_recorder = audit_recorder or AIAuditRecorder(settings.usage_dir)

    market_data = collector.collect()
    prompts = [prompt_builder.build(item) for item in market_data]
    audit_recorder.record(provider.name, provider.model, prompts)
    decisions = [
        validator.validate(provider.analyze(item, prompt))
        for item, prompt in zip(market_data, prompts)
    ]
    execution = PipelineRun(decisions=decisions)
    return execution, storage.save(execution)
