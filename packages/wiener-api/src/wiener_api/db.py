"""Engine, session, and the declarative base.

The shape is `mendel_api.db`'s, deliberately: two APIs in one repository disagreeing about how
a session is opened is a difference a reader has to hold in their head for no return. What is
*not* shared is the engine — a separate database, reached through `WIENER_DATABASE_URL`.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from wiener_api.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
