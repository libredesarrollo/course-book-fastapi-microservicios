from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from demo.microservices.user_service_client import verify_token

# Esquema de seguridad oficial de FastAPI, sin auto_error: el header
# malformado se rechaza aquí abajo con el detalle del contrato de la serie.
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no presentado o malformado",
        )
    return verify_token(credentials.credentials)
