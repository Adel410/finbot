from abc import ABC, abstractmethod

from .models import AIResponse, Decision, MarketData
from .prompt_builder import Prompt


class AIProvider(ABC):
    """Provider-neutral contract for decision providers."""

    name: str
    model: str
    dry_run: bool

    @abstractmethod
    def analyze(self, market: MarketData, prompt: Prompt | None = None) -> Decision:
        raise NotImplementedError

    @abstractmethod
    def analyze_batch(
        self, markets: list[MarketData], prompts: list[Prompt]
    ) -> AIResponse:
        raise NotImplementedError
