from config.settings import Settings

from .ai_provider import SimulatedAIProvider
from .ai_provider_contract import AIProvider
from .grok_provider import GrokAIProvider


class AIProviderFactory:
    """Select an AI provider without exposing that choice to the pipeline."""

    @staticmethod
    def create(settings: Settings) -> AIProvider:
        if settings.ai_provider == "simulated":
            return SimulatedAIProvider()
        if settings.ai_provider == "grok":
            return GrokAIProvider(
                model=settings.xai_model,
                api_key=settings.xai_api_key.get_secret_value(),
                dry_run=settings.xai_dry_run,
                max_monthly_cost_usd=settings.max_monthly_api_cost_usd,
                usage_dir=settings.usage_dir,
            )
        raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")
