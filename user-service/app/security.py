import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta


def hash_password(password: str) -> str:
    # PBKDF2 de la biblioteca estándar: sin dependencias, determinista.
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2_sha256$100000${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, _iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    # Comparación en tiempo constante: nunca `==` directo.
    return hmac.compare_digest(candidate, digest)


def issue_token() -> tuple[str, str]:
    """Devuelve (token crudo, hash para guardar). El crudo viaja una sola vez."""
    token = secrets.token_hex(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def expiry(now: datetime | None = None) -> datetime:
    from app import config

    # Naive UTC para la columna; el route lo vuelve aware al responder.
    return (now or models_now_naive()) + timedelta(minutes=config.TOKEN_TTL_MINUTES)


def models_now_naive() -> datetime:
    from app.models import utcnow

    return utcnow()
