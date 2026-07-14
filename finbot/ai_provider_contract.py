from abc import ABC, abstractmethod

from .models import Decision, MarketData
from .prompt_builder import Prompt


class AIProvider(ABC):
    """Provider-neutral contract for decision providers."""

    name: str
    model: str

    @abstractmethod
    def analyze(self, market: MarketData, prompt: Prompt | None = None) -> Decision:
        raise NotImplementedError

