import json
import logging
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app import jwt_issuer
from app.db import SessionLocal
from app.models import ApiToken
from tests.conftest import client, seed_two_users


@pytest.fixture
def jwt_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.TOKEN_MODE", "jwt")
    monkeypatch.setattr("app.config.JWT_PRIVATE_KEY_PATH", str(tmp_path / "private.pem"))
    monkeypatch.setattr("app.config.JWT_PUBLIC_KEY_PATH", str(tmp_path / "public.pem"))
    return tmp_path


def _login(c):
    return c.post(
        "/api/tokens",
        json={"email": "ana.torres@example.com", "password": "password", "device_name": "pytest"},
    )


def test_generar_par_crea_claves_y_protege_la_privada(jwt_mode, capsys):
    from app.jwt_keys import main

    main()
    privada = jwt_mode / "private.pem"
    publica = jwt_mode / "public.pem"
    assert privada.exists() and publica.exists()
    assert oct(privada.stat().st_mode & 0o777) == "0o600"
    assert "kid=" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main()  # No se sobrescribe: regenerar invalidaría los JWT vivos.


def test_login_jwt_entrega_tres_segmentos_y_no_escribe_fila(jwt_mode):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        resp = _login(c)
    assert resp.status_code == 201
    body = resp.json()
    assert body["token"].count(".") == 2
    assert body["token_type"] == "Bearer"

    db = SessionLocal()
    try:
        assert db.query(ApiToken).count() == 0
    finally:
        db.close()


def test_claims_del_jwt_y_ttl_de_quince_minutos(jwt_mode):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        token = _login(c).json()["token"]

    claims = jwt.decode(
        token, jwt_issuer.public_key(), algorithms=["RS256"], issuer="user-service"
    )
    assert claims["sub"] == "1"
    assert claims["name"] == "Ana Torres"
    assert claims["email"] == "ana.torres@example.com"
    assert claims["device_name"] == "pytest"
    assert len(claims["jti"]) == 32
    assert 14 * 60 < claims["exp"] - claims["iat"] <= 15 * 60


def test_jwks_publica_la_clave_y_el_kid_derivado(jwt_mode):
    from app.jwt_keys import main

    main()
    with client() as c:
        resp = c.get("/api/jwks.json")
    assert resp.status_code == 200
    jwk = resp.json()["keys"][0]
    assert jwk["kty"] == "RSA" and jwk["use"] == "sig" and jwk["alg"] == "RS256"
    assert jwk["kid"] == jwt_issuer.kid_for(jwt_issuer.public_key())
    assert jwk["n"] and jwk["e"] == "AQAB"


def test_jwks_sin_claves_es_503_con_comando(jwt_mode):
    with client() as c:
        resp = c.get("/api/jwks.json")
    assert resp.status_code == 503
    assert "jwt_keys" in resp.json()["detail"]


def test_login_sin_claves_es_503_con_comando(jwt_mode):
    seed_two_users()
    with client() as c:
        resp = _login(c)
    assert resp.status_code == 503
    assert "jwt_keys" in resp.json()["detail"]


def test_api_user_acepta_jwt_y_rechaza_firma_rota(jwt_mode):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        token = _login(c).json()["token"]
        ok = c.get("/api/user", headers={"Authorization": f"Bearer {token}"})
        cabeza, carga, firma = token.split(".")
        roto = f"{cabeza}.{carga}.{firma[:-1]}{'A' if firma[-1] != 'A' else 'B'}"
        malo = c.get("/api/user", headers={"Authorization": f"Bearer {roto}"})
    assert ok.status_code == 200
    assert ok.json()["id"] == 1
    assert malo.status_code == 401


def test_jwt_expirado_e_issuer_ajeno_son_401(jwt_mode):
    from app.jwt_keys import main

    main()
    seed_two_users()
    key = jwt_issuer.private_key()
    kid = jwt_issuer.kid_for(key.public_key())
    ahora = datetime.now(UTC)
    base = {"sub": "1", "name": "Ana", "email": "ana.torres@example.com", "jti": "x" * 32}

    def firmar(claims):
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})

    expirado = firmar(
        {
            **base,
            "iss": "user-service",
            "iat": ahora - timedelta(minutes=10),
            "exp": ahora - timedelta(minutes=5),
        }
    )
    ajeno = firmar(
        {**base, "iss": "otro-idp", "iat": ahora, "exp": ahora + timedelta(minutes=15)}
    )
    with client() as c:
        r_exp = c.get("/api/user", headers={"Authorization": f"Bearer {expirado}"})
        r_ajeno = c.get("/api/user", headers={"Authorization": f"Bearer {ajeno}"})
    assert r_exp.status_code == 401
    assert r_ajeno.status_code == 401


def test_revoke_con_jwt_es_204_noop_y_el_token_sigue_vivo(jwt_mode, caplog):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        token = _login(c).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        with caplog.at_level(logging.INFO, logger="user-service"):
            resp = c.delete("/api/tokens", headers=headers)
        sigue = c.get("/api/user", headers=headers)
    assert resp.status_code == 204
    assert sigue.status_code == 200
    assert any("revoke skipped" in r.getMessage() for r in caplog.records)


def test_log_de_emision_lleva_jti_pero_nunca_el_token(jwt_mode, caplog):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        with caplog.at_level(logging.INFO, logger="user-service"):
            token = _login(c).json()["token"]

    issued = [r for r in caplog.records if "API token issued" in r.getMessage()]
    assert issued
    mensaje = issued[0].getMessage()
    campos = json.loads(mensaje[mensaje.index("{") : mensaje.rindex("}") + 1])
    assert campos["mode"] == "jwt" and "jti" in campos
    assert token not in mensaje


def test_rate_limit_sigue_activo_en_modo_jwt(jwt_mode):
    from app.jwt_keys import main

    main()
    seed_two_users()
    with client() as c:
        respuestas = [_login(c) for _ in range(6)]
    assert [r.status_code for r in respuestas] == [201, 201, 201, 201, 201, 429]
