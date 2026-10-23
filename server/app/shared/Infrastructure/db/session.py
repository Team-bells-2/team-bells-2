from collections.abc import Iterator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.shared.env import settings
from app.shared.Infrastructure.db.base import Base

# Import slice models before metadata initialization so SQLAlchemy knows all tables.
from app.consent import models as consent_models  # noqa: F401
from app.customers import models as customer_models  # noqa: F401
from app.inventory import models as inventory_models  # noqa: F401
from app.ledger import models as ledger_models  # noqa: F401
from app.onboarding import models as onboarding_models  # noqa: F401
from app.suggestions import models as suggestion_models  # noqa: F401

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    # SQLite (PRD D2) connections are shared across FastAPI's worker threads.
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    from app.suggestions.seed import seed_suppliers

    with session_scope() as db:
        seed_suppliers(db)


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
