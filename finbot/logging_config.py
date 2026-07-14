import logging
from datetime import datetime
from pathlib import Path


def configure_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    """Log INFO and above to a daily file and to the console."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"finbot_{datetime.now().astimezone():%Y-%m-%d}.log"
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
        level=level,
        handlers=[file_handler, console_handler],
        force=True,
    )

