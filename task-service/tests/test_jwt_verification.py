import base64
import hashlib
import importlib
from datetime import UTC, datetime, timedelta

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

import demo.microservices.user_service_client as frontier
from demo.microservices.user_service_client.jwks import JwkKeyStore

JWKS_MODULE = importlib.import_module("demo.microservices.user_service_client.jwks")


class StubResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def _b64int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def idp(monkeypatch):
    """Un IdP falso, con clave de verdad y JWKS servida por un stub en memoria."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key()
    der = public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    kid = hashlib.sha256(der).hexdigest()[:16]
    numbers = public.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64int(numbers.n),
        "e": _b64int(numbers.e),
    }
    store = JwkKeyStore("http://idp-falso/api/jwks.json", 1, cache_ttl=3600)
    calls = {"n": 0}

    def fake_get(url, timeout):
        calls["n"] += 1
        return StubResponse(200, {"keys": [jwk]})

    monkeypatch.setattr(JWKS_MODULE, "_http_get", fake_get)
    monkeypatch.setattr(frontier, "jwks", store)
    return {"key": key, "kid": kid, "jwk": jwk, "store": store, "calls": calls, "fake_get": fake_get}


def firmar(idp, **claims) -> str:
    ahora = datetime.now(UTC)
    base = {
        "iss": "user-service",
        "sub": "7",
        "name": "Ana Torres",
        "email": "ana.torres@example.com",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=15),
        "jti": "a" * 32,
    }
    base.update(claims)
    return jwt.encode(base, idp["key"], algorithm="RS256", headers={"kid": idp["kid"]})


def test_jwt_valido_da_identidad_sin_llamar_al_idp(idp, monkeypatch):
    def prohibido(url, headers):
        raise AssertionError("Un JWT válido no debe preguntar al IdP por /api/user")

    monkeypatch.setattr(frontier, "_http_get", prohibido)
    user = frontier.verify_token(firmar(idp))
    assert user == {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}
    assert idp["calls"]["n"] == 1  # Solo se bajó la JWKS.


def test_la_jwks_se_baja_una_sola_vez(idp):
    frontier.verify_token(firmar(idp))
    frontier.verify_token(firmar(idp))
    assert idp["calls"]["n"] == 1


def test_jwt_con_firma_rota_es_401_sin_ir_a_la_red(idp, monkeypatch):
    def prohibido(url, headers):
        raise AssertionError("Un JWT inválido se rechaza localmente")

    monkeypatch.setattr(frontier, "_http_get", prohibido)
    cabeza, carga, firma = firmar(idp).split(".")
    roto = f"{cabeza}.{carga}.{firma[:-1]}{'A' if firma[-1] != 'A' else 'B'}"
    with pytest.raises(HTTPException) as ctx:
        frontier.verify_token(roto)
    assert ctx.value.status_code == 401
    assert ctx.value.detail == "Token inválido o expirado"


def test_firma_ajena_con_el_mismo_kid_es_401(idp):
    otro = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {"iss": "user-service", "sub": "7", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        otro,
        algorithm="RS256",
        headers={"kid": idp["kid"]},
    )
    with pytest.raises(HTTPException) as ctx:
        frontier.verify_token(token)
    assert ctx.value.status_code == 401


def test_expirado_issuer_ajeno_y_sin_claims_son_401(idp):
    ahora = datetime.now(UTC)
    sin_email = jwt.encode(
        {
            "iss": "user-service",
            "sub": "7",
            "name": "Ana",
            "iat": ahora,
            "exp": ahora + timedelta(minutes=15),
        },
        idp["key"],
        algorithm="RS256",
        headers={"kid": idp["kid"]},
    )
    casos = [
        firmar(idp, iat=ahora - timedelta(minutes=10), exp=ahora - timedelta(minutes=5)),
        firmar(idp, iss="otro-idp"),
        sin_email,
    ]
    for token in casos:
        with pytest.raises(HTTPException) as ctx:
            frontier.verify_token(token)
        assert ctx.value.status_code == 401


def test_cabecera_sin_kid_o_con_otro_algoritmo_es_401(idp):
    now = datetime.now(UTC)
    claims = {
        "iss": "user-service",
        "sub": "7",
        "name": "Ana",
        "email": "ana@example.com",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    sin_kid = jwt.encode(claims, idp["key"], algorithm="RS256")
    firmado_hs = jwt.encode(claims, "x" * 40, algorithm="HS256")
    for token in (sin_kid, firmado_hs):
        with pytest.raises(HTTPException) as ctx:
            frontier.verify_token(token)
        assert ctx.value.status_code == 401


def test_kid_desconocido_hace_un_solo_refetch_y_luego_401(idp):
    ahora = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "user-service",
            "sub": "7",
            "name": "Ana",
            "email": "ana@example.com",
            "iat": ahora,
            "exp": ahora + timedelta(minutes=15),
        },
        idp["key"],
        algorithm="RS256",
        headers={"kid": "kid-forjado"},
    )
    with pytest.raises(HTTPException) as ctx:
        frontier.verify_token(token)
    assert ctx.value.status_code == 401
    # Carga inicial + un único refetch por kid desconocido.
    assert idp["calls"]["n"] == 2
    for _ in range(3):
        with pytest.raises(HTTPException):
            frontier.verify_token(token)
    assert idp["calls"]["n"] == 2  # Un token forjado no martillea el IdP.


def test_jwks_caida_con_cache_fria_es_503(idp, monkeypatch):
    def caido(url, timeout):
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr(JWKS_MODULE, "_http_get", caido)
    with pytest.raises(HTTPException) as ctx:
        frontier.verify_token(firmar(idp))
    assert ctx.value.status_code == 503
    assert "JWKS" in ctx.value.detail


def test_jwks_malformada_es_503(idp, monkeypatch):
    monkeypatch.setattr(JWKS_MODULE, "_http_get", lambda url, timeout: StubResponse(500))
    with pytest.raises(HTTPException) as ctx:
        frontier.verify_token(firmar(idp))
    assert ctx.value.status_code == 503


def test_jwks_caida_con_cache_caliente_sigue_autenticando(idp, monkeypatch, caplog):
    assert frontier.verify_token(firmar(idp))["id"] == 7
    idp["store"].cache_ttl = 0  # Fuerza un refresh en la siguiente petición.

    def caido(url, timeout):
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr(JWKS_MODULE, "_http_get", caido)
    assert frontier.verify_token(firmar(idp))["id"] == 7
    assert any("refresh failed" in r.getMessage() for r in caplog.records)


def test_opaco_sigue_yendo_al_idp(idp, monkeypatch):
    llamadas = []

    def opaco(url, headers):
        llamadas.append(headers)
        return StubResponse(200, {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"})

    monkeypatch.setattr(frontier, "_http_get", opaco)
    user = frontier.verify_token("un-token-opaco-de-64-caracteres")
    assert user == {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}
    assert llamadas
    assert idp["calls"]["n"] == 0
