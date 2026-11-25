import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from app import config, jwt_issuer, security
from app.auth import require_user
from app.db import get_db
from app.models import ApiToken, User
from app.rate_limit import check_login, client_ip
from app.schemas import TokenIssued, TokenRequest, UserInfo

log = logging.getLogger("user-service")

router = APIRouter(prefix="/api")

JWT_KEYS_COMMAND = "`uv run python -m app.jwt_keys` en user-service/"


def rate_limit_login(request: Request, payload: TokenRequest) -> None:
    """Fuerza bruta contra el endpoint que recibe contraseñas: dos contadores
    con los límites y la ventana de app/config.py."""
    check_login(request, payload.email)


def issue_access_token(
    user: User, device_name: str | None, db: Session
) -> tuple[str, datetime, dict]:
    """Fachada de emisión: JWT no escribe filas, opaco guarda solo el hash."""
    if config.TOKEN_MODE == "jwt":
        try:
            token, expires_at, jti = jwt_issuer.issue(user, device_name)
        except (FileNotFoundError, TypeError) as exc:
            raise HTTPException(
                status_code=503, detail=f"{exc} Genera el par con {JWT_KEYS_COMMAND}"
            ) from exc
        return token, expires_at, {"mode": "jwt", "jti": jti}

    token, token_hash = security.issue_token()
    expires_at = security.expiry()
    row = ApiToken(
        user_id=user.id,
        token_hash=token_hash,
        name=device_name or "api-token",
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    return token, expires_at, {"mode": "opaque", "device": row.name}


@router.post(
    "/tokens",
    response_model=TokenIssued,
    status_code=201,
    dependencies=[Depends(rate_limit_login)],
)
def issue_token(
    payload: TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenIssued:
    """Inicio de sesión, una vez: credenciales → JWT firmado o token opaco."""
    user = db.query(User).filter(User.email == payload.email).first()

    # Mismo mensaje y mismo status para "no existe" y "contraseña mala": si no,
    # esta respuesta sirve para enumerar qué emails están dados de alta.
    if user is None or not security.verify_password(payload.password, user.password):
        log.warning(
            "Failed login attempt %s",
            json.dumps(
                {
                    "email": payload.email,
                    "ip": client_ip(request),
                    "account_exists": user is not None,
                },
                ensure_ascii=False,
            ),
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token, expires_at, log_fields = issue_access_token(user, payload.device_name, db)

    # Nunca el token crudo: en modo JWT se correlaciona por jti.
    log.info(
        "API token issued %s",
        json.dumps(
            {
                "user_id": user.id,
                "expires_at": expires_at.replace(tzinfo=UTC).isoformat(),
                **log_fields,
            },
            ensure_ascii=False,
        ),
    )

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
    """Revoca el token del request: con opaco borra la fila; con JWT no hay
    fila que borrar, y responde 204 tras validarlo (caduca por `exp`)."""
    from app.auth import authenticate

    user, row = authenticate(db, authorization)
    if row is None:
        log.info("API token revoke skipped %s", json.dumps({"user_id": user.id, "mode": "jwt"}))
        return

    log.info(
        "API token revoked %s",
        json.dumps({"user_id": user.id, "device": row.name, "mode": "opaque"}, ensure_ascii=False),
    )
    db.query(ApiToken).filter(ApiToken.id == row.id).delete()
    db.commit()
