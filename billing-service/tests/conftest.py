import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.deps import get_current_user
from app.main import app
from app.models import Bill

ANN = {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}


@pytest.fixture(autouse=True)
def clean_overrides():
    # Cada test arranca sin override: nadie arrastra identidad del anterior.
    app.dependency_overrides.pop(get_current_user, None)
    yield


def seed_bills(*specs: tuple[int, str, float, str]) -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        session.query(Bill).delete()
        for user_id, task_title, amount, status in specs:
            session.add(Bill(user_id=user_id, task_title=task_title, amount=amount, status=status))
        session.commit()
    finally:
        session.close()


def client_for(user: dict) -> TestClient:
    def override() -> dict:
        return user

    app.dependency_overrides[get_current_user] = override
    return TestClient(app)
