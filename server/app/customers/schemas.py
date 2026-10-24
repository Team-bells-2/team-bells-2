from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.shared.types import Money


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    # Other names the trader uses for this customer, e.g. "the rice woman" (FR-S9).
    aliases: list[str]
    created_at: datetime
    # Derived from entries on every read, never stored (FR-S10). Negative means the customer overpaid.
    balance_ngn: Money
    # Still owes, and a credit sale is past its due date (FR-S12).
    overdue: bool
