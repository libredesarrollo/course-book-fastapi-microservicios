from typing import Any

from fastapi import Header, HTTPException

from app.user_service_client import verify_token


def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    parts = authorization.split(" ", 1) if authorization else []
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
        # Header ausente o malformado: problema del cliente, se rechaza aquí
        # sin llamar a la red.
        raise HTTPException(status_code=401, detail="Token no presentado o malformado")
    return verify_token(parts[1].strip())
