import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


# Duración de vida del token opaco (capítulo 1: caducidad, 60 min).
TOKEN_TTL_MINUTES = _int("TOKEN_TTL_MINUTES", 60)
TOKEN_TTL_SECONDS = TOKEN_TTL_MINUTES * 60

# sqlite de este servicio; en tests, DATABASE_URL=sqlite:///:memory:
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.sqlite")
