from sqlalchemy.orm import Session


class BaseRepository:
    """Transaction controls for orchestrators, so they never touch Session directly.

    Repositories built in one request share the same Session (FastAPI caches
    get_db per request), so commit() on any of them commits the whole unit of work.
    """

    def __init__(self, db: Session):
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        # autoflush is off, so flush first or pending changes on the instance would be discarded.
        self.db.flush()
        self.db.refresh(instance)
