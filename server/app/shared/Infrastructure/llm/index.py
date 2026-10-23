from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.ledger.schemas import EntryData
from app.shared.env import settings

SYSTEM_PROMPT = """You extract Nigerian merchant messages into one ledger entry. Understand Nigerian Pidgin and English. Return JSON only with keys type,item,quantity,unit,amount_ngn,customer,due_date,confidence. type is sale, credit_sale, payment_received, or expense. Never invent facts. For missing amount or ambiguous customer, return null for missing fields and confidence below 0.6. A payment requires a customer. A credit sale requires a customer. A cash sale does not. due_date must be YYYY-MM-DD or null. Do not calculate totals or write explanations."""

_WORD_NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "half": 0.5,
}


def normalize_naira_shorthand(text: str) -> str:
    normalized = text.casefold()
    for word, number in _WORD_NUMBERS.items():
        normalized = re.sub(rf"\b{word}\s+k\b", f"{number}000", normalized)
    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*k\b", lambda match: str(float(match.group(1)) * 1000).rstrip("0").rstrip("."), normalized)
    return normalized


def _demo_extract(text: str, context: dict[str, Any]) -> dict[str, Any] | None:
    normalized = text.casefold()
    if context.get("pending_entry"):
        prior = dict(context["pending_entry"])
        amount_match = re.search(r"\b(\d+(?:\.\d+)?)\b", normalized)
        if amount_match and prior.get("amount_ngn") is None:
            prior["amount_ngn"] = int(amount_match.group(1))
            prior["confidence"] = 0.9
            return prior
        quantity_match = re.search(r"\b(\d+(?:\.\d+)?|one|two|three|four|five|half)\s+bags?\b", normalized)
        if quantity_match:
            quantity_value = quantity_match.group(1)
            prior["quantity"] = float(_NUMBER_WORDS.get(quantity_value, quantity_value))
            prior["confidence"] = 0.9
            return prior

    is_payment = any(phrase in normalized for phrase in ("paid me", "don pay", "pay me", "received payment"))
    is_expense = any(phrase in normalized for phrase in ("i spend", "i spent", "expense", "transport")) and not is_payment
    is_credit = any(phrase in normalized for phrase in ("on credit", "owe", "go pay", "put am for account", "she go pay"))
    entry_type = "payment_received" if is_payment else "expense" if is_expense else "credit_sale" if is_credit else "sale"

    amount_matches = list(re.finditer(r"\b(\d+(?:\.\d+)?)(?=\s*(?:ngn|naira|₦|$))|\b(\d+(?:\.\d+)?)\b", normalized))
    amount_ngn = None
    if amount_matches:
        raw_amount = amount_matches[-1].group(1) or amount_matches[-1].group(2)
        amount_ngn = int(float(raw_amount))

    quantity = None
    unit = None
    quantity_match = re.search(r"\b(\d+(?:\.\d+)?|one|two|three|four|five|half)\s+(bags?|bottles?|measures?|measures?|dericas?|painters?|pieces?)\b", normalized)
    if quantity_match:
        raw_quantity = quantity_match.group(1)
        quantity = float(_NUMBER_WORDS.get(raw_quantity, raw_quantity))
        unit = quantity_match.group(2).rstrip("s")

    item_names = ["palm oil", "vegetable oil", "tomatoes", "tomato", "garri", "beans", "rice"]
    item = next((name for name in item_names if name in normalized), None)
    if item == "tomato":
        item = "tomatoes"

    customers = context.get("customers", [])
    customer = None
    for candidate in customers:
        name = candidate.get("name", "")
        aliases = candidate.get("aliases", [])
        if any(term and term.casefold() in normalized for term in [name, *aliases]):
            customer = name
            break
    if customer is None:
        name_match = re.search(r"\b(?:to|give|for)\s+(mama\s+[a-z]+|[a-z]+\s+[a-z]+)\b", normalized)
        if name_match:
            customer = " ".join(part.capitalize() for part in name_match.group(1).split())

    if not any((item, customer, amount_ngn, quantity, is_expense)):
        return None
    confidence = 0.85 if amount_ngn is not None and (entry_type not in {"credit_sale", "payment_received"} or customer) else 0.45
    return {
        "type": entry_type,
        "item": item,
        "quantity": quantity,
        "unit": unit,
        "amount_ngn": amount_ngn,
        "customer": customer,
        "due_date": None,
        "confidence": confidence,
    }


def extract_entry(text: str, context: dict[str, Any] | None = None) -> EntryData | None:
    normalized_text = normalize_naira_shorthand(text)
    context = context or {}
    if settings.DEMO_MODE:
        demo_result = _demo_extract(normalized_text, context)
        if demo_result is not None:
            try:
                return EntryData.model_validate(demo_result)
            except ValidationError:
                return None

    if not settings.OPENAI_API_KEY:
        return None

    response = httpx.post(
        f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        json={
            "model": settings.OJA_MODEL,
            "temperature": 0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"text": normalized_text, "context": context}, ensure_ascii=False)},
            ],
        },
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()["choices"][0]["message"]["content"]
    try:
        return EntryData.model_validate_json(payload)
    except ValidationError:
        return None
