"""Firma, decodifica y publica los JWT RS256 del IdP (capítulo 10).

Las claves viven en disco, nunca en el repo. Sin ellas el modo JWT no puede
operar: se generan con `uv run python -m app.jwt_keys`.
"""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config
from app.models import User


def private_key() -> rsa.RSAPrivateKey:
    path = Path(config.JWT_PRIVATE_KEY_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}; genera el par con `uv run python -m app.jwt_keys` "
            "en user-service/"
        )
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("La clave privada del IdP debe ser RSA")
    return key


def public_key() -> rsa.RSAPublicKey:
    path = Path(config.JWT_PUBLIC_KEY_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}; genera el par con `uv run python -m app.jwt_keys` "
            "en user-service/"
        )
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, rsa.RSAPublicKey):
        raise TypeError("La clave pública del IdP debe ser RSA")
    return key


def kid_for(key: rsa.RSAPublicKey) -> str:
    """El `kid` se deriva del material público: igual clave, igual identificador."""
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def _b64int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwk_public() -> dict[str, str]:
    key = public_key()
    numbers = key.public_numbers()
    """
    • "kty": "RSA" (Key Type): Indica el tipo o familia de algoritmo criptográfico de la clave. En este caso es RSA.
    • "use": "sig" (Public Key Use): Define para qué se debe usar esta clave. "sig" significa firma digital (signature), indicando que sirve para verificar que un token o mensaje fue firmado por el dueño de la clave privada (la alternativa sería "enc" para cifrado).
    • "alg": "RS256" (Algorithm): Especifica el algoritmo exacto que se usa con esta clave. RS256 significa RSA PKCS#1 v1.5 con SHA-256.
    • "kid": kid_for(key) (Key ID): Es un identificador único (una cadena de texto o hash) para esta clave. Sirve para que, cuando un servidor publica varias claves al mismo tiempo (en un archivo llamado JWKS), el receptor sepa exactamente cuál clave usar mirando el encabezado kid del token JWT.
    • "n": _b64int(numbers.n) (Modulus): Es el módulo matemático de la clave pública RSA (el producto de dos números primos muy grandes). Como es un número entero enorme, la función _b64int lo convierte a bytes y lo codifica en Base64URL (sin signos = de relleno).
    • "e": _b64int(numbers.e) (Exponent): Es el exponente público de la clave RSA (casi siempre es el número 65537, que en Base64URL se ve como "AQAB").
    """
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid_for(key),
        "n": _b64int(numbers.n),
        "e": _b64int(numbers.e),
    }


def issue(user: User, device_name: str | None) -> tuple[str, datetime, str]:
    """Devuelve (token, expiración, jti). El token crudo se entrega una sola vez."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=config.JWT_TTL_MINUTES)
    key = private_key()
    jti = secrets.token_hex(16)
    claims = {
        "iss": config.JWT_ISSUER,
        "sub": str(user.id),
        "name": user.name,
        "email": user.email,
        "iat": now,
        "exp": expires_at,
        "jti": jti,
        "device_name": device_name or "api-token",
    }
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid_for(key.public_key())})
    return token, expires_at, jti


def decode(token: str) -> dict[str, Any]:
    """Verifica firma, issuer y expiración. `jwt.PyJWTError` se mapea en auth.py."""
    return jwt.decode(
        token,
        public_key(),
        algorithms=["RS256"],
        issuer=config.JWT_ISSUER,
        leeway=10,
        options={"require": ["exp", "iss", "sub"]},
    )
