import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.deps import get_current_user
from app.main import app
from app.models import Task

ANN = {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}


@pytest.fixture(autouse=True)
def clean_overrides():
    # Cada test arranca sin override: nadie arrastra identidad del anterior.
    app.dependency_overrides.pop(get_current_user, None)
    yield


def seed_tasks(*specs: tuple[int, str, str]) -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        session.query(Task).delete()
        for user_id, title, status in specs:
            session.add(Task(user_id=user_id, title=title, status=status))
        session.commit()
    finally:
        session.close()


def client_for(user: dict) -> TestClient:
    def override() -> dict:
        return user

    app.dependency_overrides[get_current_user] = override
    return TestClient(app)

