import logging

from config.settings import Settings, settings

from .logging_config import configure_logging
from .models import PipelineRun
from .pipeline import run_pipeline


def log_active_configuration(logger: logging.Logger, active: Settings) -> None:
    """Log non-sensitive configuration metadata only."""
    model = active.xai_model if active.ai_provider == "grok" else "deterministic-local"
    dry_run = active.xai_dry_run if active.ai_provider == "grok" else False
    logger.info("FinBot research run")
    logger.info("Market data provider: %s", active.market_data_provider)
    logger.info("AI provider: %s", active.ai_provider)
    logger.info("Model: %s", model)
    logger.info("Dry run: %s", str(dry_run).lower())
    logger.info(
        "Monthly API cost limit: %.6f USD", active.max_monthly_api_cost_usd
    )


def log_run_summary(logger: logging.Logger, run: PipelineRun, output_path) -> None:
    logger.info("Run ID: %s", run.run_id)
    logger.info("Market data provider: %s", run.market_data_provider)
    logger.info("AI provider: %s", run.ai_provider)
    logger.info("Model: %s", run.model)
    logger.info("Dry run: %s", str(run.dry_run).lower())
    logger.info("Request count: %d", run.request_count)
    logger.info("Actual cost: %s", run.actual_cost_usd)
    logger.info("-" * 38)
    for decision in run.decisions:
        logger.info(
            "%s %s confidence=%3d%% | %s",
            f"{decision.symbol:<5}",
            f"{decision.action.value:<4}",
            decision.confidence,
            decision.justification,
        )
    logger.info("-" * 38)
    logger.info("Saved to: %s", output_path)


def main() -> None:
    configure_logging(settings.logs_dir, settings.log_level)
    logger = logging.getLogger(__name__)
    log_active_configuration(logger, settings)

    try:
        execution, output_path = run_pipeline(settings.runs_dir)
        log_run_summary(logger, execution, output_path)
    except Exception:
        logger.exception("FinBot pipeline failed")
        raise
