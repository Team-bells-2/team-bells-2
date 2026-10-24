from typing import Any

from pydantic import ValidationError

from app.ai import services
from app.ai.schemas import CustomerMatch, IntentChoice, Interpretation, PhrasedReasons, ReasonFacts
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

    def match_customer(self, mention: str, text: str, customers: list[dict[str, Any]]) -> tuple[str | None, float]:
        """Which listed customer the mention means, with a confidence (FR-S9). A name not in the list is
        discarded (BR-A7). With no provider, falls back to an offline guess that must be confirmed (BR-L8)."""
        if not customers:
            return None, 0.0
        try:
            raw = self.llm_client.complete_json(services.MATCH_PROMPT, services.match_payload(mention, text, customers))
            match = CustomerMatch.model_validate(raw)
        except LLMError:
            return services.guess_customer(mention, customers)
        except ValidationError:
            return None, 0.0
        if match.customer not in {customer["name"] for customer in customers}:
            return None, 0.0
        return match.customer, match.confidence

    def route_intent(self, question: str, customers: list[str], items: list[str]) -> IntentChoice | None:
        """The model picks a whitelisted intent and parameters (FR-S11). A customer or item not in the
        trader's lists is dropped (BR-A7). None when the provider fails or the reply is invalid."""
        try:
            raw = self.llm_client.complete_json(services.INTENT_PROMPT, services.intent_payload(question, customers, items))
            choice = IntentChoice.model_validate(raw)
        except (LLMError, ValidationError):
            return None
        return choice.model_copy(
            update={
                "customer": choice.customer if choice.customer in customers else None,
                "item": choice.item if choice.item in items else None,
            }
        )

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
