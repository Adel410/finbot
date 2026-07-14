import json
import logging
import time
from pathlib import Path
from typing import Callable

import grpc
from pydantic import ValidationError
from xai_sdk import Client
from xai_sdk.chat import system, user

from .ai_audit import AICallMetrics, MonthlyBudget
from .ai_provider_contract import AIProvider
from .models import AIResponse, Decision, MarketData
from .prompt_builder import Prompt

logger = logging.getLogger(__name__)
BUDGET_WARNING_RATIO = 0.80


class GrokProviderError(RuntimeError):
    pass


class GrokConfigurationError(GrokProviderError):
    pass


class GrokDryRunError(GrokProviderError):
    pass


class GrokBudgetExceededError(GrokProviderError):
    pass


class GrokNetworkError(GrokProviderError):
    pass


class GrokTimeoutError(GrokProviderError):
    pass


class GrokAuthenticationError(GrokProviderError):
    pass


class GrokQuotaError(GrokProviderError):
    pass


class GrokAPIError(GrokProviderError):
    pass


class GrokResponseError(GrokProviderError):
    pass


class GrokAIProvider(AIProvider):
    """Official xAI SDK provider with dry-run, budget, and validation guards."""

    name = "grok"

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        dry_run: bool = True,
        max_monthly_cost_usd: float = 5.0,
        usage_dir: Path = Path("data/usage"),
        client_factory: Callable = Client,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self.dry_run = dry_run
        self.budget = MonthlyBudget(usage_dir, max_monthly_cost_usd)
        self.client_factory = client_factory
        self.timeout_seconds = timeout_seconds
        self.last_call_metrics = AICallMetrics()
        self._spent_before_call = 0.0

    def analyze(self, market: MarketData, prompt: Prompt | None = None) -> Decision:
        if prompt is None:
            raise GrokResponseError("A structured prompt is required")
        return self.analyze_batch([market], [prompt]).decisions[0]

    def analyze_batch(
        self, markets: list[MarketData], prompts: list[Prompt]
    ) -> AIResponse:
        self._validate_before_request(markets, prompts)
        self.last_call_metrics = AICallMetrics(request_count=1)
        started = time.perf_counter()
        try:
            client = self.client_factory(
                api_key=self._api_key, timeout=self.timeout_seconds
            )
            chat = client.chat.create(
                model=self.model,
                response_format=AIResponse,
                store_messages=False,
            )
            chat.append(system(prompts[0].system_prompt))
            chat.append(user("\n\n".join(prompt.user_prompt for prompt in prompts)))
            response = chat.sample()
            if not response.content or not response.content.strip():
                raise GrokResponseError("xAI returned an empty response")
            parsed = AIResponse.model_validate_json(response.content)
            expected_symbols = [market.symbol for market in markets]
            returned_symbols = [decision.symbol for decision in parsed.decisions]
            if returned_symbols != expected_symbols:
                raise GrokResponseError(
                    "xAI response symbols do not match the requested symbols"
                )
        except GrokProviderError:
            raise
        except TimeoutError:
            raise GrokTimeoutError("The xAI request timed out") from None
        except grpc.RpcError as exc:
            self._raise_grpc_error(exc)
        except (json.JSONDecodeError, ValidationError):
            raise GrokResponseError("xAI returned invalid structured JSON") from None
        except (ConnectionError, OSError):
            raise GrokNetworkError("The xAI network request failed") from None
        except Exception:
            raise GrokAPIError("The xAI API request failed") from None

        input_tokens = int(getattr(response.usage, "prompt_tokens", 0))
        output_tokens = int(getattr(response.usage, "completion_tokens", 0))
        actual_cost = response.cost_usd
        self.last_call_metrics = AICallMetrics(
            request_count=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost_usd(
                self.model, input_tokens, output_tokens
            ),
            actual_cost_usd=actual_cost,
            duration_seconds=time.perf_counter() - started,
            raw_response=response.content,
        )
        call_cost = (
            actual_cost
            if actual_cost is not None
            else self.last_call_metrics.estimated_cost_usd
        )
        self._warn_if_budget_high(self._spent_before_call + call_cost, "after")
        return parsed

    def _validate_before_request(
        self, markets: list[MarketData], prompts: list[Prompt]
    ) -> None:
        if self.dry_run:
            logger.info("Grok provider is in dry-run mode; no API request was sent.")
            raise GrokDryRunError("Grok dry run: no API request was sent")
        if not self._api_key:
            raise GrokConfigurationError("XAI_API_KEY is required")
        if not self.model:
            raise GrokConfigurationError("XAI_MODEL is required")
        if not markets or len(markets) != len(prompts):
            raise GrokResponseError("Market data and prompts must be non-empty and aligned")
        spent = self.budget.spent_usd()
        if spent >= self.budget.limit_usd:
            raise GrokBudgetExceededError(
                f"Monthly API budget is exhausted ({spent:.6f} USD used)"
            )
        self._spent_before_call = spent
        self._warn_if_budget_high(spent, "before")

    def _warn_if_budget_high(self, spent: float, stage: str) -> None:
        if spent >= self.budget.limit_usd * BUDGET_WARNING_RATIO:
            logger.warning(
                "Monthly xAI API spend is at %.1f%% of the local limit %s call "
                "(%.6f / %.6f USD).",
                spent / self.budget.limit_usd * 100,
                stage,
                spent,
                self.budget.limit_usd,
            )

    @staticmethod
    def _raise_grpc_error(exc: grpc.RpcError) -> None:
        code = exc.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise GrokTimeoutError("The xAI request timed out") from None
        if code in {grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED}:
            raise GrokAuthenticationError("xAI authentication failed") from None
        if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise GrokQuotaError("xAI quota or rate limit was exceeded") from None
        if code in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.CANCELLED}:
            raise GrokNetworkError("The xAI service is unavailable") from None
        raise GrokAPIError("The xAI API returned an error") from None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = {
        "grok-4.5": (2.0, 6.0),
        "grok-4.3": (1.25, 2.5),
        "grok-4.20": (1.25, 2.5),
    }
    matching_rate = next(
        (rate for prefix, rate in rates.items() if model.startswith(prefix)), None
    )
    if matching_rate is None:
        return 0.0
    input_rate, output_rate = matching_rate
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
