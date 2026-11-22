"""La frontera de red con el user-service, en un solo sitio (capítulo 6).

Paquete interno de la serie, consumido por task-service y billing-service.
Es el segundo paquete: nació cuando el tercer microservicio (billing)
necesitó validar tokens y el archivo `user_service_client.py` pasó a vivir
en dos sitios — la divergencia solo era cuestión de tiempo.

El contrato que fija la serie:

- `verify_token(token)` devuelve el dict de identidad `{"id", "name", "email"}`
  o lanza `HTTPException` ya mapeada: `401` si el IdP rechazó el token
  (identidad inválida, no fallo nuestro), `503` si el IdP no está en pie
  (fallo de infraestructura, con el comando para levantarlo), `502` si
  responde algo inesperado.
- Propaga el correlation ID: lee el mismo `ContextVar` que fija
  `RequestIdMiddleware` (del paquete microservices-observability) y manda
  `X-Request-Id` en cada llamada. Dos contextvars separados romperían la
  traza en silencio.
- Los warnings de la frontera salen por el logger `LOGGER_NAME`
  ("user-service-client"); cada servicio lo pasa a `configure_logging()`
  para que las líneas lleven el request_id.

La configuración es por entorno (12-factor): `USER_SERVICE_URL` y
`HTTP_TIMEOUT_SECONDS`, con los mismos defaults que usaban los servicios.
"""

import json
import logging
import os
from typing import Any

from fastapi import HTTPException
import httpx2

from demo.microservices.observability import REQUEST_ID_HEADER, request_id

LOGGER_NAME = "user-service-client"

log = logging.getLogger(LOGGER_NAME)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:8000")
HTTP_TIMEOUT_SECONDS = _env_int("HTTP_TIMEOUT_SECONDS", 2)


def _http_get(url: str, headers: dict[str, str]) -> httpx2.Response:
    with httpx2.Client(timeout=HTTP_TIMEOUT_SECONDS) as http:
        return http.get(url, headers=headers)


def _trace_headers() -> dict[str, str]:
    """Propaga el correlation ID que llegó del cliente, para que la misma
    petición pueda seguirse en los logs de los dos servicios."""
    rid = request_id.get()
    return {REQUEST_ID_HEADER: rid} if rid else {}


def verify_token(token: str) -> dict[str, Any]:
    """¿Quién es este token? Toda la frontera de red vive en este paquete:
    los demás módulos te mandan el dict del usuario como si fuera local."""
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
