from .models import Decision


class DecisionValidator:
    """Apply the Pydantic decision boundary explicitly in the pipeline."""

    def validate(self, decision: Decision) -> Decision:
        return Decision.model_validate(decision.model_dump())

