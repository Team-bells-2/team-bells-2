from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Any

import httpx
from pydantic import ValidationError

from app.ledger.schemas import EntryData
from app.shared.env import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract Nigerian merchant messages into one ledger entry. Understand Nigerian Pidgin and English. Return JSON only with keys type,item,quantity,unit,amount_ngn,customer,due_date,confidence. type is sale, credit_sale, payment_received, or expense. Never invent facts. For missing amount or ambiguous customer, return null for missing fields and confidence below 0.6. A payment requires a customer. A credit sale requires a customer. A cash sale does not. "two bags and half" means quantity 2.5. If context.customers lists a customer whose name or alias the message refers to, use that customer's name exactly. If context.pending_entry is present, the message answers the clarifying question for that entry: return the completed entry. due_date must be YYYY-MM-DD or null; resolve weekday names against context.today. Do not calculate totals or write explanations."""

CORRECTION_PROMPT = """The merchant is correcting their last ledger entry, given as context.last_entry. Return JSON only with the keys from item,quantity,unit,amount_ngn,customer,due_date that the message changes, using the new values. Leave out every key the message does not change. Understand Nigerian Pidgin and English."""

MATCH_PROMPT = """Decide which existing customer a merchant's message refers to. context.customers lists each customer's name and aliases. Return JSON only: {"customer": <exact name from the list or null>, "confidence": <0 to 1>}. Use null when the mention is a new person."""

INTENT_PROMPT = """Route a Nigerian merchant's question (Pidgin or English) to one intent. Allowed intents: who_owes, customer_balance, today_total, stock_level, restock_suggestion, unknown. Return JSON only: {"intent": ..., "customer": <name from context.customers or null>, "item": <name from context.items or null>}. Never answer the question yourself."""

REASON_PROMPT = """Write one short sentence (under 20 words) explaining why this supplier is recommended, using only the facts given. Write in light Nigerian Pidgin mixed with simple English, the way a Lagos market trader talks. Keep every number, price, name and unit exactly as given, written as digits. Do not add or change any number. Return JSON only: {"reason": "..."}."""

CORRECTION_PATTERN = re.compile(r"^\s*(no+[,.!]?\s+(i\s+mean|na|e\s+be|be)|i\s+mean|correction|actually|sorry[,.]?\s+(i\s+mean|na|e\s+be)|abeg\s+change|change\s+am)\b")

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
_UNITS = r"bags?|bottles?|measures?|dericas?|painters?|pieces?|tins?|kg|litres?|cartons?|baskets?|packets?|packs?|crates?|sachets?|kegs?|bundles?|dozens?|tubers?|paints?|rolls?"
_QUANTITY = r"\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|half"
_ITEM_NAMES = ["palm oil", "vegetable oil", "groundnut oil", "tomatoes", "tomato", "garri", "beans", "rice", "yam", "oil"]


def normalize_naira_shorthand(text: str) -> str:
    normalized = text.casefold()
    for word, number in _WORD_NUMBERS.items():
        normalized = re.sub(rf"\b{word}\s+k\b", f"{number}000", normalized)
    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*k\b", lambda match: str(float(match.group(1)) * 1000).rstrip("0").rstrip("."), normalized)
    normalized = re.sub(r"(?<=\d),(?=\d{3}\b)", "", normalized)
    return normalized


def is_correction(text: str) -> bool:
    return bool(CORRECTION_PATTERN.search(text.casefold()))


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return unit
    unit = unit.strip().casefold()
    return unit[:-1] if unit.endswith("s") and unit not in {"kg"} else unit


def _quantity(normalized: str) -> tuple[float | None, str | None]:
    match = re.search(rf"\b({_QUANTITY})\s+({_UNITS})(\s+and\s+(a\s+)?half)?\b", normalized)
    if not match:
        return None, None
    raw = match.group(1)
    quantity = float(_NUMBER_WORDS.get(raw, raw))
    if match.group(3):
        quantity += 0.5
    return quantity, normalize_unit(match.group(2))


def _amount(normalized: str, quantity: float | None) -> int | None:
    without_quantity = re.sub(rf"\b({_QUANTITY})\s+({_UNITS})(\s+and\s+(a\s+)?half)?\b", " ", normalized)
    numbers = [float(value) for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?!\w|\.\d)", without_quantity)]
    numbers = [value for value in numbers if value >= 50 or quantity is None]
    return int(numbers[-1]) if numbers else None


_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TITLES = {"mama", "papa", "mr", "mrs", "aunty", "auntie", "uncle", "the", "oga", "madam", "brother", "sister", "iya", "baba"}


def _due_date(normalized: str, today_iso: str | None) -> str | None:
    today = date.fromisoformat(today_iso) if today_iso else date.today()
    if re.search(r"\btomorrow\b|\btmrw\b", normalized):
        return (today + timedelta(days=2 if "next tomorrow" in normalized else 1)).isoformat()
    if re.search(r"\bnext\s+week\b", normalized):
        return (today + timedelta(days=7)).isoformat()
    for index, day in enumerate(_WEEKDAYS):
        if re.search(rf"\b{day}\b", normalized):
            return (today + timedelta(days=(index - today.weekday()) % 7 or 7)).isoformat()
    return None


def _match_known_customer(normalized: str, customers: list[dict[str, Any]]) -> str | None:
    """The one customer whose name or alias appears; None when there are none or several (the caller asks)."""
    matches = [
        candidate.get("name", "") for candidate in customers
        if any(term and re.search(rf"\b{re.escape(term.casefold())}\b", normalized) for term in [candidate.get("name", ""), *candidate.get("aliases", [])])
    ]
    full_names = [name for name in matches if re.search(rf"\b{re.escape(name.casefold())}\b", normalized)]
    if len(full_names) == 1:
        return full_names[0]
    return matches[0] if len(matches) == 1 else None


def _demo_extract(text: str, context: dict[str, Any]) -> dict[str, Any] | None:
    normalized = text.casefold()
    if context.get("pending_entry"):
        prior = dict(context["pending_entry"])
        prior.pop("raw_text", None)
        if prior.get("amount_ngn") is None:
            amount = _amount(normalized, None)
            if amount is not None:
                prior["amount_ngn"] = amount
        if prior.get("customer") is None:
            short_name = len(text.split()) <= 3 and not re.search(r"\d", text) and not re.search(r"\b(yes|no|ok|yeah|nope|correct|which|who|what|how)\b", normalized)
            needs_customer = prior.get("type") in {"credit_sale", "payment_received"}
            prior["customer"] = _match_known_customer(normalized, context.get("customers", [])) or (text.strip().title() if short_name and needs_customer else None)
        quantity, unit = _quantity(normalized)
        if quantity is not None:
            prior["quantity"], prior["unit"] = quantity, unit
        complete = prior.get("amount_ngn") is not None and (prior.get("type") not in {"credit_sale", "payment_received"} or prior.get("customer"))
        prior["confidence"] = 0.9 if complete else prior.get("confidence", 0.45)
        return prior

    is_credit = any(phrase in normalized for phrase in ("on credit", "owe", "go pay", "put am for account", "will pay", "credit", "pay later", "pay me later", "account"))
    is_payment = not is_credit and any(phrase in normalized for phrase in ("paid me", "don pay", "pay me", "received payment", "pay back", "paid"))
    is_expense = any(phrase in normalized for phrase in ("i spend", "i spent", "expense", "transport", "i buy", "i bought", "go buy", "went buy", "i don buy", "restock", "i purchase", "i purchased")) and not is_payment
    entry_type = "payment_received" if is_payment else "expense" if is_expense else "credit_sale" if is_credit else "sale"

    quantity, unit = _quantity(normalized)
    amount_ngn = _amount(normalized, quantity)

    # Nicknames such as "the rice woman" must not count as the item sold.
    item_text = normalized
    for candidate in context.get("customers", []):
        for term in [candidate.get("name", ""), *candidate.get("aliases", [])]:
            if term:
                item_text = item_text.replace(term.casefold(), " ")
    item = next((name for name in _ITEM_NAMES if re.search(rf"\b{name}\b", item_text)), None)
    if item == "tomato":
        item = "tomatoes"
    if item is None and (named := re.search(rf"\b(?:{_QUANTITY})\s+(?:{_UNITS})(?:\s+and\s+(?:a\s+)?half)?\s+(?:of\s+)?([a-z][a-z-]+)", item_text)):
        # Any goods named right after "one packet of ...", e.g. Pepsi.
        if named.group(1) not in {"for", "to", "give", "at", "on", "and", "na", "with"}:
            item = named.group(1)

    customer = _match_known_customer(normalized, context.get("customers", []))
    known_mentions = sum(
        any(term and re.search(rf"\b{re.escape(term.casefold())}\b", normalized) for term in [candidate.get("name", ""), *candidate.get("aliases", [])])
        for candidate in context.get("customers", [])
    )
    # Several known customers share the words used: leave the customer empty so the trader is asked.
    if customer is None and known_mentions == 0 and (payer := re.search(r"\b([a-z]+)\s+(?:don\s+pay|don\s+pay\s+me|paid\s+me|pay\s+me|paid)\b", normalized)):
        if payer.group(1) not in {"she", "he", "e", "i", "dem", "they", "customer", "woman", "man", "don", "go", "will", "to", "and", "just"}:
            customer = payer.group(1).capitalize()
    if customer is None and known_mentions == 0 and (account := re.search(r"\bon\s+([a-z]+)'s\s+account\b", normalized)):
        customer = account.group(1).capitalize()
    if customer is None and known_mentions == 0:
        name_match = re.search(r"\b(mama\s+[a-z]+|papa\s+[a-z]+|mr\.?\s+[a-z]+|mrs\.?\s+[a-z]+|aunty\s+[a-z]+|uncle\s+[a-z]+|iya\s+[a-z]+|baba\s+[a-z]+|oga\s+[a-z]+)\b", normalized)
        if name_match:
            customer = " ".join(part.capitalize() for part in name_match.group(1).split())

    if not any((item, customer, amount_ngn, quantity, is_expense)):
        return None
    confidence = 0.85 if amount_ngn is not None and (entry_type not in {"credit_sale", "payment_received"} or customer) else 0.45
    return {
        "type": entry_type, "item": item, "quantity": quantity, "unit": unit,
        "amount_ngn": amount_ngn, "customer": customer,
        "due_date": _due_date(normalized, context.get("today")) if entry_type == "credit_sale" else None,
        "confidence": confidence,
    }


def _demo_correction(text: str, last_entry: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_naira_shorthand(text)
    changes: dict[str, Any] = {}
    # "No be 2 bags, na 4 bags" means the last value; "55k, not 60k" means the first.
    pick_first = bool(re.search(r"\bnot\b", normalized))
    quantities = list(re.finditer(rf"\b({_QUANTITY})\s+({_UNITS})(\s+and\s+(a\s+)?half)?\b", normalized))
    if len(quantities) > 1:
        chosen = quantities[0] if pick_first else quantities[-1]
        normalized = normalized[:quantities[0].start()] + chosen.group(0) + " " + normalized[quantities[-1].end():]
    amounts = re.findall(r"(?<![\w.])(\d{3,}(?:\.\d+)?)(?!\w|\.\d)", normalized)
    if len(amounts) > 1:
        changes["amount_ngn"] = int(float(amounts[0] if pick_first else amounts[-1]))
    quantity, unit = _quantity(normalized)
    if quantity is not None:
        changes["quantity"] = quantity
        changes["unit"] = unit or last_entry.get("unit")
    elif (bare := re.search(rf"\b(?:mean|na|be)\s+({_QUANTITY})\b(?!\s*000)", normalized)) and float(_NUMBER_WORDS.get(bare.group(1), bare.group(1))) < 50:
        changes["quantity"] = float(_NUMBER_WORDS.get(bare.group(1), bare.group(1)))
    amount = _amount(normalized, quantity)
    if "amount_ngn" not in changes and amount is not None and amount >= 50:
        changes["amount_ngn"] = amount
    item = next((name for name in _ITEM_NAMES if re.search(rf"\b{name}\b", normalized)), None)
    if item and item != last_entry.get("item"):
        changes["item"] = "tomatoes" if item == "tomato" else item
    return changes


_CACHE: dict[str, dict[str, Any] | None] = {}
_CACHE_LIMIT = 500
CALL_COUNT = 0


def _chat_json(system_prompt: str, payload: dict[str, Any], max_tokens: int = 800) -> dict[str, Any] | None:
    """Single wrapper for every LLM call (NFR-8): cache, call counter, timeout, token cap, JSON output."""
    global CALL_COUNT
    if settings.DEMO_MODE or not settings.OPENAI_API_KEY:
        return None
    key = json.dumps([settings.OJA_MODEL, system_prompt, payload], ensure_ascii=False, default=str, sort_keys=True)
    if key in _CACHE:
        return _CACHE[key]
    for attempt in range(2):
        CALL_COUNT += 1
        response = _post_chat(system_prompt, payload, max_tokens)
        # Free tiers rate-limit bursts: wait once, briefly, then let the caller fall back.
        if response.status_code == 429 and attempt == 0:
            retry_after = response.headers.get("retry-after", "")
            time.sleep(min(float(retry_after), 3.0) if retry_after.replace(".", "", 1).isdigit() else 1.5)
            continue
        break
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = parsed
    return parsed


def _post_chat(system_prompt: str, payload: dict[str, Any], max_tokens: int) -> httpx.Response:
    return httpx.post(
        f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        json={
            "model": settings.OJA_MODEL,
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
        },
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def _validate(result: dict[str, Any] | None) -> EntryData | None:
    if result is None:
        return None
    try:
        return EntryData.model_validate(result)
    except ValidationError:
        return None


def extract_entry(text: str, context: dict[str, Any] | None = None) -> EntryData | None:
    normalized_text = normalize_naira_shorthand(text)
    context = context or {}
    try:
        for _ in range(2):  # FR-S3: one retry, then the caller asks a question
            result = _chat_json(SYSTEM_PROMPT, {"text": normalized_text, "context": context})
            if result is None and (settings.DEMO_MODE or not settings.OPENAI_API_KEY):
                break
            entry = _validate(result)
            if entry is not None:
                # Dates are computed in code: models miscount weekdays.
                due = _due_date(normalized_text, context.get("today"))
                if entry.type == "credit_sale" and due:
                    entry = entry.model_copy(update={"due_date": date.fromisoformat(due)})
                return entry
        else:
            return None
    except httpx.HTTPError as error:
        logger.warning("LLM extraction failed, using rule-based fallback: %s", error)
    return _validate(_demo_extract(normalized_text, context))


def extract_correction(text: str, last_entry: dict[str, Any]) -> dict[str, Any]:
    allowed = {"item", "quantity", "unit", "amount_ngn", "customer", "due_date"}
    try:
        result = _chat_json(CORRECTION_PROMPT, {"text": normalize_naira_shorthand(text), "context": {"last_entry": last_entry}})
    except httpx.HTTPError as error:
        logger.warning("LLM correction failed, using rule-based fallback: %s", error)
        result = None
    if result is None:
        return _demo_correction(text, last_entry)
    return {key: value for key, value in result.items() if key in allowed and value is not None}


def match_customer(text: str, customers: list[dict[str, Any]]) -> tuple[str | None, float]:
    """Alias lookup already failed; ask the model which known customer is meant."""
    if not customers:
        return None, 0.0
    try:
        result = _chat_json(MATCH_PROMPT, {"text": text, "context": {"customers": customers}}, max_tokens=400)
    except httpx.HTTPError:
        result = None
    if result is None:
        # Offline fallback: a distinctive word of a known name ("Ngozi" in "Mama Ngozi") is a guess to confirm, never a link.
        words = set(re.findall(r"[a-z]+", text.casefold()))
        guesses = [customer["name"] for customer in customers if (set(customer["name"].casefold().split()) - _TITLES) & words]
        return (guesses[0], 0.6) if len(guesses) == 1 else (None, 0.0)
    names = {customer["name"] for customer in customers}
    name = result.get("customer")
    confidence = result.get("confidence")
    if name not in names or not isinstance(confidence, int | float):
        return None, 0.0
    return name, float(confidence)


def route_intent(question: str, customers: list[str], items: list[str]) -> dict[str, Any] | None:
    try:
        result = _chat_json(INTENT_PROMPT, {"question": question, "context": {"customers": customers, "items": items}}, max_tokens=400)
    except httpx.HTTPError:
        return None
    if result is None or result.get("intent") not in {"who_owes", "customer_balance", "today_total", "stock_level", "restock_suggestion", "unknown"}:
        return None
    if result.get("customer") not in customers:
        result["customer"] = None
    if result.get("item") not in items:
        result["item"] = None
    return result


def phrase_reason(facts: dict[str, Any]) -> str | None:
    try:
        result = _chat_json(REASON_PROMPT, {"facts": facts}, max_tokens=400)
    except httpx.HTTPError:
        return None
    reason = result.get("reason") if result else None
    return reason.strip() if isinstance(reason, str) and reason.strip() else None
