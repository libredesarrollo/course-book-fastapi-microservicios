"""Correlation ID y logs con contexto (capítulo 4).

task-service lleva una copia exacta de este módulo: los dos servicios son
proyectos uv independientes y no comparten código. El contrato es el mismo
que fija la serie: `X-Request-Id` se respeta si llega del cliente (o del
servicio que nos llama) y se genera si no; siempre sale en la respuesta; y
queda al alcance de cualquier log de la petición sin pasarlo a mano.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-Id"

# El middleware lo fija al entrar y lo resetea al salir; cualquier código
# de la petición (incluidas las llamadas salientes al otro servicio) lo
# lee de aquí sin tener que tocar la request.
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class RequestIdFilter(logging.Filter):
    """Inyecta el request_id de la petición en cada record del logger donde
    se cuelga: el log de negocio lo lleva sin pasarlo a mano.

    Va en el logger y no en el handler porque los filtros de un handler no
    alcanzan a los records que ve caplog en los tests.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get() or "-"
        return True


class RequestIdFormatter(logging.Formatter):
    """Imprime el request_id de la línea; "-" cuando el record no nació
    dentro de una petición (arranque, seed, logs de librerías)."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


def configure_logging(*loggers: str) -> None:
    """INFO visible y request_id en cada línea del handler de raíz."""
    logging.basicConfig(level=logging.INFO)
    formatter = RequestIdFormatter(
        "%(levelname)s:%(name)s:%(message)s request_id=%(request_id)s"
    )
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)
    for name in loggers:
        logging.getLogger(name).addFilter(RequestIdFilter())
