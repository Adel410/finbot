from .ai_provider_contract import AIProvider
from .models import Decision, MarketData
from .prompt_builder import Prompt


class GrokProviderError(RuntimeError):
    """Base exception reserved for a future Grok integration."""


class GrokConfigurationError(GrokProviderError):
    """Reserved for future missing or invalid Grok configuration."""


class GrokResponseError(GrokProviderError):
    """Reserved for future invalid Grok responses."""


class GrokAIProvider(AIProvider):
    """Non-operational placeholder; it cannot perform network calls."""

    name = "grok"

    def __init__(self, model: str = "", api_key: str = "", dry_run: bool = True) -> None:
        self.model = model
        self.api_key = api_key
        self.dry_run = dry_run

    def analyze(self, market: MarketData, prompt: Prompt | None = None) -> Decision:
        raise NotImplementedError(
            "Grok is intentionally unavailable in Sprint 3A; no request was sent."
        )

