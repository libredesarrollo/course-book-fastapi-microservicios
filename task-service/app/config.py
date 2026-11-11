import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


# Dónde vive el IdP. En producción, variable de entorno; en dev, puerto 8000.
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:8000")
HTTP_TIMEOUT_SECONDS = _int("HTTP_TIMEOUT_SECONDS", 2)

# sqlite de este servicio; en tests, DATABASE_URL=sqlite:///:memory:
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.sqlite")
