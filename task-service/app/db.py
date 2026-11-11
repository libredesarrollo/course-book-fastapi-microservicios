from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


def _make_engine(url: str) -> "create_engine":  # type: ignore[valid-type]
    kwargs = {"connect_args": {"check_same_thread": False}}
    if url.endswith("//:memory:"):
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _make_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
