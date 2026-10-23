"""Eval adapter (FR-S18): runs the F1 extraction pipeline on one message without a database.

    PYTHONPATH=server python eval/run_eval.py --adapter app.ai.index:extract_message
"""

from __future__ import annotations

from typing import Any

from app.ledger.index import _missing_question
from app.shared.Infrastructure.llm.index import extract_correction, extract_entry, is_correction, normalize_naira_shorthand

MISSING_FIELDS = {"How much": "amount_ngn", "Which customer": "customer", "I didn't fully": "confidence"}


def _plural(unit: str | None, quantity: float | None) -> str | None:
    return f"{unit}s" if unit and quantity is not None and quantity > 1 and not unit.endswith("s") and unit != "kg" else unit


def extract_message(text: str, context: dict[str, Any]) -> dict[str, Any]:
    text = normalize_naira_shorthand(text)
    last_entry = context.get("last_entry")
    if last_entry and is_correction(text):
        changes = extract_correction(text, last_entry)
        entry = {**last_entry, **changes}
        entry["unit"] = _plural(entry.get("unit"), entry.get("quantity"))
        return {"status": "corrected" if changes else "needs_clarification", "entry": entry}

    data = extract_entry(text, context)
    if data is None:
        return {"status": "needs_clarification", "question": "Please say what happened and how much.", "missing_fields": []}
    question = _missing_question(data)
    if question:
        missing = [field for prefix, field in MISSING_FIELDS.items() if question.startswith(prefix)]
        return {"status": "needs_clarification", "question": question, "missing_fields": missing}
    entry = {key: value for key, value in data.model_dump(mode="json").items() if value is not None and key != "confidence"}
    if "quantity" in entry and float(entry["quantity"]).is_integer():
        entry["quantity"] = int(entry["quantity"])
    entry["unit"] = _plural(data.unit, data.quantity)
    return {"status": "recorded", "entry": {key: value for key, value in entry.items() if value is not None}}
