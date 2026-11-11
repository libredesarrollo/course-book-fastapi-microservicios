import logging
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app import security
from app.auth import require_user
from app.db import get_db
from app.models import ApiToken, User, utcnow
from app.schemas import TokenIssued, TokenRequest, UserInfo

log = logging.getLogger("user-service")

router = APIRouter(prefix="/api")


@router.post("/tokens", response_model=TokenIssued, status_code=201)
def issue_token(
    payload: TokenRequest,
    db: Session = Depends(get_db),
) -> TokenIssued:
    """Inicio de sesión, una vez: email + contraseña → token opaco que caduca."""
    user = db.query(User).filter(User.email == payload.email).first()

    # Mismo mensaje y mismo status para "no existe" y "contraseña mala": si no,
    # esta respuesta sirve para enumerar qué emails están dados de alta.
    if user is None or not security.verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token, token_hash = security.issue_token()
    expires_at = security.expiry()
    row = ApiToken(
        user_id=user.id,
        token_hash=token_hash,
        name=payload.device_name or "api-token",
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()

    return TokenIssued(
        token=token,
        token_type="Bearer",
        expires_at=expires_at.replace(tzinfo=UTC),
        user=UserInfo.model_validate(user),
    )


@router.get("/user", response_model=UserInfo)
def whoami(user: User = Depends(require_user)) -> UserInfo:
    return UserInfo.model_validate(user)


@router.delete("/tokens", status_code=204)
def revoke(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Revoca el token con el que se hizo el request: borrar la fila es una
    revocación real e inmediata (el trade-off del token opaco)."""
    from app.auth import authenticate

    user, row = authenticate(db, authorization)
    log.info("Token revocado", extra={"user_id": user.id, "device": row.name})
    db.query(ApiToken).filter(ApiToken.id == row.id).delete()
    db.commit()
