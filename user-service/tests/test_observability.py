import logging
import uuid

from tests.conftest import client, seed_two_users


def test_health_no_pide_autenticacion_ni_toca_la_bd():
    r = client().get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "user-service"
    assert "timestamp" in r.json()


def test_toda_respuesta_lleva_un_request_id_generado():
    r = client().get("/health")

    rid = r.headers["X-Request-Id"]
    assert uuid.UUID(rid).version == 4


def test_respeta_el_request_id_del_cliente():
    r = client().get("/health", headers={"X-Request-Id": "prueba-trazabilidad-123"})

    assert r.headers["X-Request-Id"] == "prueba-trazabilidad-123"


def test_el_request_id_llega_a_los_logs_de_negocio(caplog):
    seed_two_users()
    rid = "prueba-trazabilidad-001"

    with caplog.at_level(logging.INFO, logger="user-service"):
        client().post(
            "/api/tokens",
            json={"email": "ana.torres@example.com", "password": "mala"},
            headers={"X-Request-Id": rid},
        )

    records = [r for r in caplog.records if "Failed login attempt" in r.getMessage()]
    assert records
    assert all(r.request_id == rid for r in records)
