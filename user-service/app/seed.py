"""Usuarios demo de la primera parte (los mismos de la serie Laravel):

    uv run python -m app.seed
"""

from sqlalchemy.orm import Session

from app import security
from app.db import Base, engine, SessionLocal
from app.models import User

DEMO_USERS = [
    {"name": "Ana Torres", "email": "ana.torres@example.com", "password": "password"},
    {"name": "Luis Ramirez", "email": "luis.ramirez@example.com", "password": "password"},
]


def run() -> None:
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    try:
        for spec in DEMO_USERS:
            exists = db.query(User).filter(User.email == spec["email"]).first()
            if exists:
                continue
            db.add(
                User(
                    name=spec["name"],
                    email=spec["email"],
                    password=security.hash_password(spec["password"]),
                )
            )
        db.commit()
        users = db.query(User).count()
        print(f"{users} usuario(s) en la base de datos")
    finally:
        db.close()


if __name__ == "__main__":
    run()
