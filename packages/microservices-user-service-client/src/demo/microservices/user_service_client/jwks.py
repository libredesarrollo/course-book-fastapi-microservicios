"""JWKS del IdP con caché por proceso (capítulo 10).

Un solo sitio decide cuándo se baja la clave pública: al arrancar en frío,
cuando caduca la caché o cuando aparece un `kid` nuevo (rotación). Un `kid`
desconocido provoca como máximo un refetch; si sigue sin aparecer, se trata
como token inválido para que un JWT forjado no pueda martillear el IdP.
"""

import logging
import os
import time
from typing import Any

import httpx2
import jwt

log = logging.getLogger("user-service-client")


class JwksUnavailable(Exception):
    """No se pudo obtener la JWKS: fallo de infraestructura, no de identidad."""


class UnknownKid(Exception):
    """La clave del token no está en la JWKS publicada."""


def _http_get(url: str, timeout: float) -> httpx2.Response:
    with httpx2.Client(timeout=timeout) as http:
        return http.get(url)


class JwkKeyStore:
    def __init__(self, url: str, timeout: float, cache_ttl: int | None = None) -> None:
        self.url = url
        self.timeout = timeout
        self.cache_ttl = cache_ttl or int(os.environ.get("USER_SERVICE_JWKS_CACHE_TTL", "3600"))
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0
        self._refetched: set[str] = set()

    def _fetch(self) -> None:
        try:
            resp = _http_get(self.url, self.timeout)
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise JwksUnavailable(str(exc)) from exc

        if resp.status_code != 200:
            raise JwksUnavailable(f"JWKS HTTP {resp.status_code}")

        try:
            keys = resp.json()["keys"]
            parsed = {str(jwk["kid"]): jwt.algorithms.RSAAlgorithm.from_jwk(jwk) for jwk in keys}
        except (KeyError, TypeError, ValueError, jwt.PyJWTError) as exc:
            raise JwksUnavailable("JWKS malformada") from exc

        if not parsed:
            raise JwksUnavailable("JWKS sin claves")

        self._keys = parsed
        self._fetched_at = time.monotonic()

    def key(self, kid: str) -> Any:
        now = time.monotonic()
        if not self._keys:
            self._fetch()
        elif now - self._fetched_at > self.cache_ttl:
            try:
                self._fetch()
            except JwksUnavailable as exc:
                # Con caché caliente el IdP puede caer sin tumbar la auth.
                log.warning("JWKS refresh failed, using cached keys: %s", exc)

        if kid not in self._keys and kid not in self._refetched:
            self._refetched.add(kid)
            self._fetch()

        if kid not in self._keys:
            raise UnknownKid(kid)
        return self._keys[kid]
