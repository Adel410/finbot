from config.settings import Settings
from finbot.ai_provider import SimulatedAIProvider
from finbot.ai_provider_factory import AIProviderFactory
from finbot.grok_provider import GrokAIProvider


def test_factory_selects_simulated_provider() -> None:
    assert isinstance(
        AIProviderFactory.create(Settings(ai_provider="simulated")),
        SimulatedAIProvider,
    )


def test_factory_selects_non_operational_grok_provider() -> None:
    assert isinstance(
        AIProviderFactory.create(
            Settings(ai_provider="grok", xai_model="grok-test", xai_dry_run=True)
        ),
        GrokAIProvider,
    )
