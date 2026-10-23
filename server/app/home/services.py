from collections.abc import Iterable
from decimal import Decimal


def profit(revenue: Decimal, expenses: Decimal) -> Decimal:
    """PRD model: revenue minus expenses, no cost of goods; may be negative (FR-S27).
    Payments received are not revenue, because the credit sale already counted."""
    return revenue - expenses


def total_owed(balances: Iterable[Decimal]) -> Decimal:
    """Sum of what customers owe; an overpaying customer does not reduce what others owe."""
    return sum((balance for balance in balances if balance > 0), Decimal(0))
