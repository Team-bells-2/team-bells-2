from collections.abc import Iterator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.shared.env import settings
from app.shared.Infrastructure.db.base import Base

# Import slice models before metadata initialization so SQLAlchemy knows all tables.
from app.customers import models as customer_models  # noqa: F401
from app.inventory import models as inventory_models  # noqa: F401
from app.ledger import models as ledger_models  # noqa: F401
from app.onboarding import models as onboarding_models  # noqa: F401

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
