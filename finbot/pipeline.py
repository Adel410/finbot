from pathlib import Path

from config.settings import settings

from .ai_provider import SimulatedAIProvider
from .market_data import MarketDataCollector, create_market_data_collector
from .models import PipelineRun
from .prompt_builder import PromptBuilder
from .storage import RunStorage
from .validator import DecisionValidator


def run_pipeline(
    runs_dir: Path = Path("data/runs"),
    collector: MarketDataCollector | None = None,
) -> tuple[PipelineRun, Path]:
    collector = collector or create_market_data_collector(settings.market_data_provider)
    prompt_builder = PromptBuilder()
    provider = SimulatedAIProvider()
    validator = DecisionValidator()
    storage = RunStorage(runs_dir)

    market_data = collector.collect()
    prompts = [prompt_builder.build(item) for item in market_data]
    decisions = [
        validator.validate(provider.analyze(item))
        for item, _prompt in zip(market_data, prompts)
    ]
    execution = PipelineRun(decisions=decisions)
    return execution, storage.save(execution)
