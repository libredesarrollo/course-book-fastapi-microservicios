"""Verificación local del JWT: la segunda implementación del contrato.

Devuelve el mismo dict `{"id", "name", "email"}` que el camino HTTP, sin
saltar a la red por petición. Los errores se separan en dos clases: los de
identidad (firma, `iss`, `exp`, `kid` desconocido) y los de infraestructura
(JWKS no disponible con la caché fría), que el dispatcher mapea distinto.
"""

import os
from typing import Any

import jwt

from .jwks import JwkKeyStore, UnknownKid

ISSUER = os.environ.get("JWT_ISSUER", "user-service")
LEEWAY = 10


def verify(token: str, store: JwkKeyStore) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise jwt.InvalidTokenError("cabecera JWT inesperada")

    # UnknownKid y JwksUnavailable salen sin convertir: son casos distintos.
    key = store.key(header["kid"])
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=ISSUER,
        leeway=LEEWAY,
        options={"require": ["exp", "iss", "sub", "name", "email"]},
    )
    return {
        "id": int(claims["sub"]),
        "name": str(claims["name"]),
        "email": str(claims["email"]),
    }


__all__ = ["ISSUER", "LEEWAY", "UnknownKid", "verify"]
