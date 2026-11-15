import logging
import uuid

import httpx2
from fastapi.testclient import TestClient

from app.main import app


class StubResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_health_no_pide_autenticacion_ni_toca_la_bd():
    with TestClient(app) as c:
        r = c.get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "task-service"
    assert "timestamp" in r.json()


def test_respeta_el_request_id_del_cliente():
    with TestClient(app) as c:
        r = c.get("/health", headers={"X-Request-Id": "prueba-trazabilidad-123"})

    assert r.headers["X-Request-Id"] == "prueba-trazabilidad-123"


def test_propaga_al_user_service_el_request_id_del_cliente(monkeypatch):
    captured: dict = {}

    def espia(url, headers):
        captured["headers"] = headers
        # 401 basta: la cabecera ya salió, y así el test no toca la BD.
        return StubResponse(401)

    monkeypatch.setattr("app.user_service_client._http_get", espia)

    with TestClient(app) as c:
        c.get("/api/tasks", headers={"X-Request-Id": "traza-e2e-001", "Authorization": "Bearer t"})

    assert captured["headers"]["X-Request-Id"] == "traza-e2e-001"


def test_propaga_al_user_service_el_request_id_generado(monkeypatch):
    captured: dict = {}

    def espia(url, headers):
        captured["headers"] = headers
        return StubResponse(401)

    monkeypatch.setattr("app.user_service_client._http_get", espia)

    with TestClient(app) as c:
        c.get("/api/tasks", headers={"Authorization": "Bearer t"})

    rid = captured["headers"]["X-Request-Id"]
    assert uuid.UUID(rid).version == 4


def test_el_request_id_llega_a_los_logs_de_la_frontera(caplog, monkeypatch):
    def caido(url, headers):
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr("app.user_service_client._http_get", caido)

    with caplog.at_level(logging.INFO, logger="task-service"):
        with TestClient(app) as c:
            c.get(
                "/api/tasks",
                headers={"X-Request-Id": "traza-e2e-002", "Authorization": "Bearer t"},
            )

    # El caso del capítulo: el IdP caído deja warning, y el request_id dice
    # qué cliente lo provocó.
    records = [r for r in caplog.records if "user-service unreachable" in r.getMessage()]
    assert records
    assert all(r.request_id == "traza-e2e-002" for r in records)
