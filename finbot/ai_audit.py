import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .prompt_builder import Prompt


class AICallMetrics(BaseModel):
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float | None = None
    duration_seconds: float = 0.0
    raw_response: str = ""


class AIAuditRecord(BaseModel):
    run_id: str = Field(min_length=32, max_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    prompts: list[Prompt]
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float | None = None
    duration_seconds: float = 0.0
    raw_response: str = ""


class AIAuditRecorder:
    """Persist prompts, sanitized responses, usage, cost, and duration locally."""

    def __init__(self, usage_dir: Path) -> None:
        self.usage_dir = usage_dir

    def record(
        self,
        run_id: str,
        provider: str,
        model: str,
        prompts: list[Prompt],
        metrics: AICallMetrics | None = None,
    ) -> Path:
        metrics = metrics or AICallMetrics()
        record = AIAuditRecord(
            run_id=run_id,
            provider=provider,
            model=model,
            prompts=prompts,
            **metrics.model_dump(),
        )
        self.usage_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.usage_dir / f"ai_audit_{run_id}.json"
        output_path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return output_path


class MonthlyBudget:
    """Calculate current-month API spend from ignored local audit files."""

    def __init__(self, usage_dir: Path, limit_usd: float) -> None:
        self.usage_dir = usage_dir
        self.limit_usd = limit_usd

    def spent_usd(self, now: datetime | None = None) -> float:
        month = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
        total = 0.0
        for path in self.usage_dir.glob("ai_audit_*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if str(payload.get("created_at", "")).startswith(month):
                    actual = payload.get("actual_cost_usd")
                    total += float(
                        actual
                        if actual is not None
                        else payload.get("estimated_cost_usd", 0.0)
                    )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return total
