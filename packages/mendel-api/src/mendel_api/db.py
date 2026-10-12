"""Engine, session, and the declarative base."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from mendel_api.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # `ck` gives every CHECK a name a migration can refer to; `ix` is SQLAlchemy's default
    # spelled out, so no existing index is renamed (issue 274).
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
    })


from mendel_api import shapes  # noqa: E402 — after Base, which it listens on

shapes.install(Base)


_joined: ContextVar[Session | None] = ContextVar("mendel_db_joined", default=None)
"""The transaction an action opened (`transaction()`), which every scope beneath it joins."""


def in_transaction() -> bool:
    return _joined.get() is not None


@contextmanager
def transaction() -> Iterator[Session]:
    """**One action, one transaction** (spec §11.2 of the consultant build). Every
    `session_scope()` opened beneath this one joins it as a savepoint, and nothing commits until
    this exits. An exception out of it rolls back everything the action wrote."""
    if _joined.get() is not None:
        raise RuntimeError("a transaction is already open: an action never starts another")
    session = SessionLocal()
    token = _joined.set(session)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        _joined.reset(token)
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """A unit of work: its own transaction, or, inside an action's, a savepoint of it.

    **A savepoint, not a plain join**, so code that catches an exception from a scope (a refusal
    it expected) sees what it saw before: that scope wrote nothing, and earlier ones stand."""
    joined = _joined.get()
    if joined is not None:
        with joined.begin_nested():
            yield joined
        return
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
