import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import authenticate
from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture(autouse=True)
def limitador_limpio():
    # Que nadie arrastre los contadores del login del test anterior.
    from app.rate_limit import reset

    reset()
    yield
    reset()


def seed_two_users() -> None:
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    try:
        from app.models import ApiToken

        db.query(ApiToken).delete()
        db.query(User).delete()
        for spec in [
            ("Ana Torres", "ana.torres@example.com"),
            ("Luis Ramirez", "luis.ramirez@example.com"),
        ]:
            db.add(
                User(name=spec[0], email=spec[1], password=hash_password("password"))
            )
        db.commit()
    finally:
        db.close()


def client() -> TestClient:
    return TestClient(app)
