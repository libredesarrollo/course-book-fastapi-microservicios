import logging

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app import security
from app.db import get_db
from app.models import ApiToken, User, utcnow

log = logging.getLogger("user-service")


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


def authenticate(db: Session, authorization: str | None) -> tuple[User, ApiToken]:
    """¿Quién es este token? La respuesta es `401` ante token inválido o expirado."""
    token = _bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Token no presentado o malformado")

    row = db.query(ApiToken).filter(ApiToken.token_hash == security.hash_token(token)).first()
    if row is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    # Token caducado: para el cliente es idéntico a uno inexistente.
    if row.expires_at <= utcnow():
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    return row.user, row


def require_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    user, _ = authenticate(db, authorization)
    return user
