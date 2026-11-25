"""La clave pública del IdP, para que los RPs verifiquen sin saltar a la red."""

from fastapi import APIRouter, HTTPException

from app import jwt_issuer

router = APIRouter(prefix="/api")


@router.get("/jwks.json")
def jwks() -> dict:
    try:
        return {"keys": [jwt_issuer.jwk_public()]}
    except (FileNotFoundError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc} Levántalo con `uv run python -m app.jwt_keys` en user-service/",
        ) from exc
