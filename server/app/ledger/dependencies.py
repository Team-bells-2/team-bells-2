from fastapi import Depends
from sqlalchemy.orm import Session

from app.ledger.repositories.clarification_repository import ClarificationRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.ledger.repositories.processed_message_repository import ProcessedMessageRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_entry_repository(db: Session = Depends(get_db)) -> EntryRepository:
    return EntryRepository(db)


def get_clarification_repository(db: Session = Depends(get_db)) -> ClarificationRepository:
    return ClarificationRepository(db)


def get_processed_message_repository(db: Session = Depends(get_db)) -> ProcessedMessageRepository:
    return ProcessedMessageRepository(db)
