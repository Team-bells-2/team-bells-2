from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ChatMessageOut(BaseModel):
    id: int
    role: Literal["trader", "assistant"]
    text: str
    entry_id: int | None
    created_at: datetime


class ChatHistory(BaseModel):
    """Oldest first. `has_more` is true when older messages exist (ask again with before_id)."""

    messages: list[ChatMessageOut]
    has_more: bool
