import re
from decimal import Decimal

from app.ai.schemas import IntentChoice
from app.ask.schemas import OwingCustomer
from app.suggestions.schemas import SupplierSuggestion

FALLBACK_ANSWER = "I can tell you who owes you, one customer's balance, today's sales, your stock, or where to restock."
DEMO_ITEMS = ("rice", "beans", "garri", "oil")

# Keyword routing on the normalised question, tried before the model (BR-Q1).
_RESTOCK = re.compile(r"where (i|i fit|can i|to|should i)\s*(fit\s+)?(buy|get|restock)|restock|who (dey|de|is) sell")
_BALANCE = re.compile(r"\b(how much|wetin)\b.*\b(owe|dey owe)\b")
_WHO_OWES = re.compile(r"who (owes|dey owe|de owe|still owe)|who never pay|my debtors")
_TODAY = re.compile(r"(sell|sold|sales|make)\b.*\btoday\b|today('s)? sales")
_STOCK = re.compile(r"\b(stock|remain|left|how many)\b")


def normalise(question: str) -> str:
    return " ".join(question.casefold().strip().rstrip("?!.").split())


def keyword_intent(question: str, customers: list[str], items: list[str]) -> IntentChoice | None:
    """Cheap routing for common phrasings; None leaves it to the model (BR-Q1)."""
    words = question.split()
    customer = next(
        (name for name in customers if name.casefold() in question or name.casefold().split()[-1] in words), None
    )
    item = next((name for name in items if name.casefold() in question), None)
    if _RESTOCK.search(question):
        fallback_item = next((name for name in DEMO_ITEMS if re.search(rf"\b{name}\b", question)), None)
        return IntentChoice(intent="restock_suggestion", item=item or fallback_item)
    if _BALANCE.search(question) and customer:
        return IntentChoice(intent="customer_balance", customer=customer)
    if _WHO_OWES.search(question):
        return IntentChoice(intent="who_owes")
    if _TODAY.search(question):
        return IntentChoice(intent="today_total")
    if _STOCK.search(question) and item:
        return IntentChoice(intent="stock_level", item=item)
    return None


def naira(amount: Decimal) -> str:
    return f"₦{amount:,.0f}" if amount == amount.to_integral_value() else f"₦{amount:,.2f}"


def who_owes_answer(owing: list[OwingCustomer]) -> str:
    """Largest debt first, "(overdue)" marker, then the total (BR-Q2)."""
    if not owing:
        return "Nobody owes you right now."
    parts = [f"{c.name} {naira(c.balance_ngn)}{' (overdue)' if c.overdue else ''}" for c in owing]
    return f"{'; '.join(parts)}. Total {naira(sum((c.balance_ngn for c in owing), Decimal(0)))}."


def customer_balance_answer(customer: OwingCustomer) -> str:
    if customer.balance_ngn > 0:
        return f"{customer.name} owes you {naira(customer.balance_ngn)}{' (overdue)' if customer.overdue else ''}."
    return f"{customer.name} doesn't owe you anything."


def today_answer(sales: Decimal) -> str:
    return f"Today's recorded sales are {naira(sales)}."


def stock_answer(item: str, quantity: Decimal, unit: str) -> str:
    amount = quantity.normalize()
    plural = unit if amount == 1 or unit.endswith("s") or unit.casefold() == "kg" else f"{unit}s"
    return f"You have {amount:f} {plural} of {item} left."


def restock_answer(item: str, suggestions: list[SupplierSuggestion]) -> str:
    if not suggestions:
        return f"I don't have supplier data for {item} yet."
    lines = [
        f"{index}. {s.supplier_name} ({s.area}), {naira(s.unit_price_ngn)} per {s.unit}: {s.reason}"
        for index, s in enumerate(suggestions, start=1)
    ]
    return "Demo data. " + " ".join(lines)


def how_many_question(item: str) -> str:
    """No quantity to rank for and none is guessed (BR-S1)."""
    return f"How many {item} do you need? Set a reorder quantity for {item}, or use Where to restock with a quantity."
