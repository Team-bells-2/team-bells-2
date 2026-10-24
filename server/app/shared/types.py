from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Stored as Numeric (exact); sent to clients as JSON numbers.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Quantity = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
