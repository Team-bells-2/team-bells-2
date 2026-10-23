from typing import Any

from pydantic import ValidationError

from app.ai import services
from app.ai.schemas import Interpretation, PhrasedReasons, ReasonFacts
from app.shared.Infrastructure.llm.client import LLMClient, LLMError


class InterpretationFailed(Exception):
    """The model's output failed validation twice (FR-S3)."""


class AIOrchestrator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def interpret_message(self, text: str, context: dict[str, Any]) -> Interpretation:
        """Validate model output against the schema; on invalid output retry once, then give up.
        Provider failures (LLMError) are not retried and propagate to the caller."""
        previous_error: str | None = None
        for _ in range(2):
            raw = self.llm_client.complete_json(
                services.INTERPRET_PROMPT, services.interpret_payload(text, context, previous_error)
            )
            try:
                return Interpretation.model_validate(raw)
            except ValidationError as error:
                previous_error = f"Invalid output: {error.errors()[0].get('msg', 'schema mismatch')}"
        raise InterpretationFailed(previous_error or "Invalid output.")

    def phrase_reasons(self, facts: list[ReasonFacts]) -> list[str] | None:
        """Wording only. Returns None on any failure so the caller uses its template (FR-S31)."""
        if not facts:
            return []
        try:
            raw = self.llm_client.complete_json(services.REASONS_PROMPT, services.reasons_payload(facts))
            reasons = PhrasedReasons.model_validate(raw).reasons
        except (LLMError, ValidationError):
            return None
        if len(reasons) != len(facts) or not all(reason.strip() for reason in reasons):
            return None
        return [reason.strip() for reason in reasons]
