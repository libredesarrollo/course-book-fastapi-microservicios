from typing import Any

from fastapi import Header, HTTPException

from app.user_service_client import verify_token

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any

# 1. Define el esquema de seguridad oficial de FastAPI
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    # credentials.scheme será "Bearer" y credentials.credentials será el token limpio
    token = credentials.credentials
    
    print(token) # Para verificar que llega bien
    
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token no presentado o malformado"
        )
    return user_data


# def get_current_user(
#     authorization: str | None = Header(default=None, alias="Authorization"),
# ) -> dict[str, Any]:
#     parts = authorization.split(" ", 1) if authorization else []
#     print(authorization)
#     if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
#         raise HTTPException(status_code=401, detail="Token no presentado o malformado")
#     return verify_token(parts[1].strip())
