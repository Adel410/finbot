import logging

from config.settings import settings

from .logging_config import configure_logging
from .pipeline import run_pipeline


def main() -> None:
    """Run the local pipeline and print a concise console summary."""
    configure_logging(settings.logs_dir, settings.log_level)
    logger = logging.getLogger(__name__)

    try:
        execution, output_path = run_pipeline(settings.runs_dir)
        logger.info("FinBot — %s market research run", settings.market_data_provider)
        logger.info("-" * 38)
        for decision in execution.decisions:
            logger.info(
                "%s %s confidence=%3d%% | %s",
                f"{decision.symbol:<5}",
                f"{decision.action.value:<4}",
                decision.confidence,
                decision.justification,
            )
        logger.info("-" * 38)
        logger.info("Saved to: %s", output_path)
    except Exception:
        logger.exception("FinBot pipeline failed")
        raise
