import json
import logging
from typing import Any

from fastapi import HTTPException
import httpx2

from app import config
from app.observability import REQUEST_ID_HEADER, request_id

log = logging.getLogger("task-service")


def _http_get(url: str, headers: dict[str, str]) -> httpx2.Response:
    with httpx2.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as http:
        return http.get(url, headers=headers)


def _trace_headers() -> dict[str, str]:
    """Propaga el correlation ID que llegó del cliente, para que la misma
    petición pueda seguirse en los logs de los dos servicios."""
    rid = request_id.get()
    return {REQUEST_ID_HEADER: rid} if rid else {}


def verify_token(token: str) -> dict[str, Any]:
    """¿Quién es este token? Toda la frontera de red vive en este archivo:
    los demás módulos te mandan el dict del usuario como si fuera local."""
    try:
        resp = _http_get(
            f"{config.USER_SERVICE_URL}/api/user",
            headers={"Authorization": f"Bearer {token}", **_trace_headers()},
        )
    except (httpx2.ConnectError, httpx2.ConnectTimeout):
        # El warning lleva el request_id del cliente: sin él, un IdP caído
        # deja un error sin saber qué petición lo provocó.
        log.warning(
            "user-service unreachable %s",
            json.dumps(
                {"base_url": config.USER_SERVICE_URL, "path": "/api/user"},
                ensure_ascii=False,
            ),
        )
        # Es un fallo de infraestructura, no de identidad: el cliente merece
        # saber qué servicio falta y cómo levantarlo (503, no `401` genérico).
        raise HTTPException(
            status_code=503,
            detail=(
                "user-service no está en pie (se esperaba "
                f"{config.USER_SERVICE_URL}); levántalo con "
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
