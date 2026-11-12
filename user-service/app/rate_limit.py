import hashlib
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app import config

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    # La IP del socket, no de las cabeceras: detrás de un proxy esto es la
    # trampa del capítulo (todas las peticiones compartirían presupuesto).
    return request.client.host if request.client else "unknown"


def _email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def check_login(request: Request, email: str) -> None:
    """Dos contadores porque son dos ataques distintos:
    - por IP: un barrido de muchas cuentas desde un mismo origen;
    - por cuenta (clave email+IP): una sola cuenta martilleada desde una IP.
    Cuenta TODO intento, no solo los fallidos: un límite que solo frena los
    errores es decorativo, basta acertar en el intento 21."""
    now = time.monotonic()
    ip = client_ip(request)
    pairs = (
        (f"ip:{ip}", config.LOGIN_THROTTLE_PER_IP),
        (f"email:{_email_key(email)}|ip:{ip}", config.LOGIN_THROTTLE_PER_ACCOUNT),
    )
    with _lock:
        for key, limit in pairs:
            hits = _hits[key]
            while hits and now - hits[0] >= config.LOGIN_THROTTLE_DECAY_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                wait = int(config.LOGIN_THROTTLE_DECAY_SECONDS - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail="Demasiados intentos de login; inténtalo más tarde",
                    headers={"Retry-After": str(wait)},
                )
        for key, _limit in pairs:
            _hits[key].append(now)


def reset() -> None:
    with _lock:
        _hits.clear()
