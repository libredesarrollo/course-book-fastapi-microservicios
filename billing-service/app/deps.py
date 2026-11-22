from typing import Any

from fastapi import Header, HTTPException

from demo.microservices.user_service_client import verify_token


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    parts = authorization.split(" ", 1) if authorization else []
    # El header malformado se rechaza aquí, sin llamar a la red.
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Token no presentado o malformado")
    return verify_token(parts[1].strip())
