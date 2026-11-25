"""La frontera con el user-service, en un solo sitio (capítulos 6 y 10).

Paquete interno de la serie, consumido por task-service y billing-service.
Es el segundo paquete: nació cuando el tercer microservicio (billing)
necesitó validar tokens y el archivo `user_service_client.py` pasó a vivir
en dos sitios — la divergencia solo era cuestión de tiempo.

El contrato que fija la serie:

- `verify_token(token)` devuelve el dict de identidad `{"id", "name", "email"}`
  o lanza `HTTPException` ya mapeada: `401` si la identidad no es válida,
  `503` si falta infraestructura, `502` si el IdP responde algo inesperado.
  Los RPs no saben si el token era JWT u opaco: se decide por su forma.
- JWT (tres segmentos separados por puntos): firma RS256 verificada con la
  JWKS cacheada, sin salto de red por petición. Sin caché y con el IdP caído
  no se puede verificar: fallo cerrado con 503.
- Opaco: `GET /api/user` al IdP, propagando el correlation ID del mismo
  `ContextVar` que fija `RequestIdMiddleware` (paquete observabilidad).
  En modo JWT esa cabecera ya no cruza: no hay petición por token.
- Los warnings salen por el logger `LOGGER_NAME` ("user-service-client");
  cada servicio lo pasa a `configure_logging()` para que lleven request_id.

Configuración por entorno: `USER_SERVICE_URL`, `HTTP_TIMEOUT_SECONDS` y
`USER_SERVICE_JWKS_CACHE_TTL`.
"""

import json
import logging
import os
from typing import Any

from fastapi import HTTPException
import httpx2
import jwt

from demo.microservices.observability import REQUEST_ID_HEADER, request_id

from .jwks import JwkKeyStore, JwksUnavailable, UnknownKid
from .jwt_verifier import verify as verify_jwt

LOGGER_NAME = "user-service-client"

log = logging.getLogger(LOGGER_NAME)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:8000")
HTTP_TIMEOUT_SECONDS = _env_int("HTTP_TIMEOUT_SECONDS", 2)

# Un store por proceso, igual que el rate limit del IdP: la JWKS se baja una
# vez y se comparte entre todas las peticiones que atiende este worker.
jwks = JwkKeyStore(f"{USER_SERVICE_URL}/api/jwks.json", HTTP_TIMEOUT_SECONDS)


def _http_get(url: str, headers: dict[str, str]) -> httpx2.Response:
    with httpx2.Client(timeout=HTTP_TIMEOUT_SECONDS) as http:
        return http.get(url, headers=headers)


def _trace_headers() -> dict[str, str]:
    """Propaga el correlation ID que llegó del cliente, para que la misma
    petición pueda seguirse en los logs de los dos servicios."""
    rid = request_id.get()
    return {REQUEST_ID_HEADER: rid} if rid else {}


def _verify_opaque(token: str) -> dict[str, Any]:
    """El camino del capítulo 2: preguntar al IdP por el token opaco."""
    try:
        resp = _http_get(
            f"{USER_SERVICE_URL}/api/user",
            headers={"Authorization": f"Bearer {token}", **_trace_headers()},
        )
    except (httpx2.ConnectError, httpx2.ConnectTimeout):
        # El warning lleva el request_id del cliente: sin él, un IdP caído
        # deja un error sin saber qué petición lo provocó.
        log.warning(
            "user-service unreachable %s",
            json.dumps(
                {"base_url": USER_SERVICE_URL, "path": "/api/user"},
                ensure_ascii=False,
            ),
        )
        # Es un fallo de infraestructura, no de identidad: el cliente merece
        # saber qué servicio falta y cómo levantarlo (503, no `401` genérico).
        raise HTTPException(
            status_code=503,
            detail=(
                "user-service no está en pie (se esperaba "
                f"{USER_SERVICE_URL}); levántalo con "
                "`uv run uvicorn app.main:app --port 8000` en user-service/"
            ),
        )

    if resp.status_code == 200:
        user = resp.json()
        # El cliente del IdP devuelve {id, name, email}; nada más entra aquí.
        return {"id": int(user["id"]), "name": str(user["name"]), "email": str(user["email"])}

    if resp.status_code == 401:
        # La distinción que importa: `401` NO es un fallo del servicio, es
        # identidad inválida del token presentado.
        log.warning("Token rejected by user-service")
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    log.warning(
        "Unexpected response from user-service %s",
        json.dumps({"status": resp.status_code}, ensure_ascii=False),
    )
    raise HTTPException(
        status_code=502,
        detail=f"Respuesta inesperada del user-service (HTTP {resp.status_code})",
    )


def verify_token(token: str) -> dict[str, Any]:
    """¿Quién es este token? Un JWT se verifica aquí; un opaco va al IdP.

    Lo que no cambia es el contrato: los RPs siguen recibiendo el dict de
    identidad y las mismas HTTPException de siempre.
    """
    if token.count(".") != 2:
        return _verify_opaque(token)

    try:
        return verify_jwt(token, jwks)
    except JwksUnavailable as exc:
        # Sin clave pública no hay verificación posible: es infraestructura,
        # no una identidad inválida. Nunca se degrada a 401.
        log.warning(
            "JWKS unavailable %s",
            json.dumps({"url": jwks.url, "error": str(exc)}, ensure_ascii=False),
        )
        raise HTTPException(
            status_code=503,
            detail="No se pudo obtener la JWKS del user-service; sin clave pública no se puede verificar el token",
        ) from exc
    except (UnknownKid, jwt.PyJWTError, ValueError, TypeError) as exc:
        # Firma rota, exp, iss ajeno, kid desconocido...: identidad inválida,
        # y por tanto 401 SIN llamar al IdP.
        log.warning("JWT rejected locally")
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
