import logging

import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app import jwt_issuer, security
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


def _jwt_user(token: str, db: Session) -> User:
    """Un JWT no tiene fila: se verifica localmente con la clave pública."""
    try:
        claims = jwt_issuer.decode(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user = db.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return user


def authenticate(db: Session, authorization: str | None) -> tuple[User, ApiToken | None]:
    """¿Quién es este token? La respuesta es `401` ante token inválido o expirado.

    El JWT se reconoce por su forma (tres segmentos) y se verifica aquí mismo;
    el opaco sigue buscando su fila. `None` en el segundo valor = sin fila.
    """
    token = _bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Token no presentado o malformado")

    if token.count(".") == 2:
        return _jwt_user(token, db), None

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
