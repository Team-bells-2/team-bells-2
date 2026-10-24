from fastapi import Depends
from sqlalchemy.orm import Session

from app.chat.repositories.chat_repository import ChatRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_chat_repository(db: Session = Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)
