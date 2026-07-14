import json
from pathlib import Path

from .models import PipelineRun


class RunStorage:
    """Persist validated pipeline runs as local JSON files."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    def save(self, run: PipelineRun) -> Path:
        return save_run(run, self.runs_dir)


def save_run(run: PipelineRun, runs_dir: Path = Path("data/runs")) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    output_path = runs_dir / f"run_{run.run_id}.json"
    output_path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return output_path
