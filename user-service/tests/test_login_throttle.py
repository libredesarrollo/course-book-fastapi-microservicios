import logging

import pytest

from tests.conftest import SessionLocal, client, seed_two_users
from app.models import ApiToken, User
from app.security import hash_password


def _login(c, email: str = "ana.torres@example.com", password: str = "password"):
    return c.post(
        "/api/tokens",
        json={"email": email, "password": password, "device_name": "pytest"},
    )


def _otra_ip(monkeypatch, ip: str) -> None:
    monkeypatch.setattr("app.rate_limit.client_ip", lambda request: ip)


def test_corta_en_el_sexto_intento_por_cuenta():
    seed_two_users()
    with client() as c:
        codes = [_login(c, password=f"intento-{i}").status_code for i in range(1, 7)]
    assert codes == [401, 401, 401, 401, 401, 429]


def test_el_429_avisa_cuanto_falta():
    seed_two_users()
    with client() as c:
        for i in range(1, 7):
            resp = _login(c, password=f"intento-{i}")
    assert resp.status_code == 429
    retry = resp.headers["Retry-After"]
    assert retry.isdigit() and 0 < int(retry) <= 60


def test_cada_cuenta_tiene_su_propio_presupuesto():
    seed_two_users()
    with client() as c:
        for i in range(1, 7):
            resp = _login(c, password=f"intento-{i}")
        assert resp.status_code == 429
        # Ana está bloqueada; a Luis desde la misma IP no lo castiga nadie.
        luis = _login(c, email="luis.ramirez@example.com", password="password")
    assert luis.status_code == 201


def test_un_barrido_de_muchas_cuentas_corta_en_20():
    # Ningún email existe: el límite por cuenta nunca puede activarse.
    with client() as c:
        codes = [
            _login(c, email=f"barrido-{i}@example.com", password="loquesea").status_code
            for i in range(1, 25)
        ]
    assert codes[:20] == [401] * 20
    assert codes[20:] == [429] * 4


def test_bloquea_tambien_la_contrasena_correcta():
    seed_two_users()
    with client() as c:
        for i in range(1, 6):
            _login(c, password=f"intento-{i}")
        # La quinta fue fallida; la correcta es el sexto intento y el límite
        # cuenta TODO intento, no solo los errores.
        resp = _login(c)
    assert resp.status_code == 429


def test_un_intento_fallido_no_emite_ningun_token():
    seed_two_users()
    with client() as c:
        for i in range(1, 4):
            _login(c, password=f"intento-{i}")
    db = SessionLocal()
    try:
        assert db.query(ApiToken).count() == 0
    finally:
        db.close()


def test_las_ips_no_comparten_presupuesto(monkeypatch):
    seed_two_users()
    _otra_ip(monkeypatch, "203.0.113.7")
    with client() as c:
        for i in range(1, 6):
            _login(c, password=f"intento-{i}")
        _otra_ip(monkeypatch, "203.0.113.9")
        # Otra IP: presupuesto fresco, también para la misma cuenta
        # (la clave por cuenta lleva la IP).
        resp = _login(c, password="intento-1")
    assert resp.status_code == 401


def test_registra_email_ip_y_existencia_de_la_cuenta(caplog):
    seed_two_users()
    with caplog.at_level(logging.WARNING, logger="user-service"):
        with client() as c:
            _login(c, password="wrong")
            _login(c, email="fantasma@example.com", password="wrong")
    textos = [r.getMessage() for r in caplog.records if "Failed login attempt" in r.getMessage()]
    assert len(textos) == 2
    assert '"email": "ana.torres@example.com"' in textos[0]
    assert '"ip": "testclient"' in textos[0]
    assert '"account_exists": true' in textos[0]
    assert '"account_exists": false' in textos[1]


def test_nunca_registra_la_contrasena(caplog):
    seed_two_users()
    with caplog.at_level(logging.WARNING, logger="user-service"):
        with client() as c:
            _login(c, password="mi-secreto-muy-largo")
    assert "mi-secreto-muy-largo" not in caplog.text


def test_el_limite_viene_de_la_configuracion(monkeypatch):
    from app import config, rate_limit

    assert config.LOGIN_THROTTLE_PER_ACCOUNT == 5
    assert config.LOGIN_THROTTLE_PER_IP == 20
    assert config.LOGIN_THROTTLE_DECAY_SECONDS == 60
