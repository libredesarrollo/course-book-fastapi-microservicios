from datetime import timedelta

from tests.conftest import client, seed_two_users


def _login(c):
    return c.post(
        "/api/tokens",
        json={"email": "ana.torres@example.com", "password": "password"},
    ).json()


def test_quien_es_este_token():
    seed_two_users()
    with client() as c:
        token = _login(c)["token"]
        resp = c.get("/api/user", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "name": "Ana Torres", "email": "ana.torres@example.com"}


def test_token_invalido_y_malformado_son_401():
    seed_two_users()
    with client() as c:
        fake = c.get("/api/user", headers={"Authorization": "Bearer " + "0" * 64})
        nada = c.get("/api/user")
        sin_bearer = c.get("/api/user", headers={"Authorization": "Basic abc"})
    assert fake.status_code == 401
    assert nada.status_code == 401
    assert sin_bearer.status_code == 401


def test_token_expirado_es_401_como_cualquier_otro():
    seed_two_users()
    from datetime import UTC, datetime

    with client() as c:
        token = _login(c)["token"]
        # Un token existente, pero que ya venció.
        from app.db import SessionLocal
        from app.models import ApiToken, utcnow

        db = SessionLocal()
        try:
            # Vencen TODOS los tokens: el row del token actual es el del final.
            for row in db.query(ApiToken).all():
                row.expires_at = utcnow() - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        resp = c.get("/api/user", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token inválido o expirado"


def test_revoke_mata_el_token_de_inmediato():
    seed_two_users()
    with client() as c:
        token = _login(c)["token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert c.get("/api/user", headers=headers).status_code == 200
        resp = c.delete("/api/tokens", headers=headers)
        assert resp.status_code == 204
        # La fila se borró: revocación real e inmediata.
        assert c.get("/api/user", headers=headers).status_code == 401
