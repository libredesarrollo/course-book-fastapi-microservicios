import base64
import hashlib
import importlib
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import demo.microservices.user_service_client as frontier
from demo.microservices.user_service_client.jwks import JwkKeyStore
from app.main import app

JWKS_MODULE = importlib.import_module("demo.microservices.user_service_client.jwks")


class StubResponse:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _b64int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def jwt_listo(monkeypatch):
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
    monkeypatch.setattr(
        JWKS_MODULE, "_http_get", lambda url, timeout: StubResponse({"keys": [jwk]})
    )
    monkeypatch.setattr(
        frontier, "jwks", JwkKeyStore("http://idp-falso/api/jwks.json", 1)
    )
    ahora = datetime.now(UTC)
    claims = {
        "iss": "user-service",
        "sub": "7",
        "name": "Ana Torres",
        "email": "ana.torres@example.com",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=15),
        "jti": "b" * 32,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def test_billing_acepta_jwt_y_toma_el_dueno_del_sub(jwt_listo):
    with TestClient(app) as c:
        resp = c.post(
            "/api/bills",
            headers={"Authorization": f"Bearer {jwt_listo}"},
            json={"task_title": "Informe", "amount": 10.0, "user_id": 999},
        )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == 7
    assert resp.json()["task_title"] == "Informe"


def test_billing_rechaza_jwt_roto_sin_llamar_al_idp(jwt_listo, monkeypatch):
    def prohibido(url, headers):
        raise AssertionError("Un JWT roto se rechaza en el paquete, sin HTTP")

    monkeypatch.setattr(frontier, "_http_get", prohibido)
    cabeza, carga, firma = jwt_listo.split(".")
    roto = f"{cabeza}.{carga}.{firma[:-1]}{'A' if firma[-1] != 'A' else 'B'}"
    with TestClient(app) as c:
        resp = c.get("/api/bills", headers={"Authorization": f"Bearer {roto}"})
    assert resp.status_code == 401
