import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .prompt_builder import Prompt


class AIAuditRecord(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    prompts: list[Prompt]
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class AIAuditRecorder:
    """Write a local audit record; it performs no usage or network operation."""

    def __init__(self, usage_dir: Path) -> None:
        self.usage_dir = usage_dir

    def record(self, provider: str, model: str, prompts: list[Prompt]) -> Path:
        record = AIAuditRecord(provider=provider, model=model, prompts=prompts)
        self.usage_dir.mkdir(parents=True, exist_ok=True)
        timestamp = record.created_at.strftime("%Y%m%dT%H%M%S_%fZ")
        output_path = self.usage_dir / f"ai_audit_{timestamp}.json"
        output_path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return output_path

