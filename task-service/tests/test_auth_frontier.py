import httpx2
import pytest

from app.user_service_client import verify_token


class StubResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_verifica_la_frontera_sincrona(monkeypatch):
    monkeypatch.setattr(
        "app.user_service_client._http_get",
        lambda url, headers: StubResponse(
            200, {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}
        ),
    )
    user = verify_token("f4k3t0k3n")
    assert user == {"id": 7, "name": "Ana Torres", "email": "ana.torres@example.com"}


def test_el_401_del_idp_es_identidad_invalida_no_fallo_aqui(monkeypatch):
    monkeypatch.setattr(
        "app.user_service_client._http_get",
        lambda url, headers: StubResponse(401),
    )
    with pytest.raises(Exception) as ctx:
        verify_token("bad")
    assert getattr(ctx.value, "status_code", None) == 401
    assert ctx.value.detail == "Token inválido o expirado"


def test_idp_caido_es_503_y_dice_como_levantarlo(monkeypatch):
    def caido(url, headers):
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr("app.user_service_client._http_get", caido)
    with pytest.raises(Exception) as ctx:
        verify_token("whatever")
    assert getattr(ctx.value, "status_code", None) == 503
    assert "user-service" in ctx.value.detail
    assert "uvicorn" in ctx.value.detail


def test_respuesta_rara_del_idp_es_502(monkeypatch):
    monkeypatch.setattr(
        "app.user_service_client._http_get",
        lambda url, headers: StubResponse(500),
    )
    with pytest.raises(Exception) as ctx:
        verify_token("whatever")
    assert getattr(ctx.value, "status_code", None) == 502
    assert "Respuesta inesperada" in ctx.value.detail


def test_header_malformado_es_401_sin_llamar_a_nadie(monkeypatch):
    from app.main import app

    called = {"n": 0}

    def espia(url, headers):
        called["n"] += 1
        return StubResponse(200, {"id": 7, "name": "A", "email": "a@example.com"})

    monkeypatch.setattr("app.user_service_client._http_get", espia)

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/api/tasks")
    assert r.status_code == 401
    assert r.json()["detail"] == "Token no presentado o malformado"
    assert called["n"] == 0
