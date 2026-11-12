from tests.conftest import client, seed_two_users


def _login(c, email: str = "ana.torres@example.com", password: str = "password"):
    return c.post(
        "/api/tokens",
        json={"email": email, "password": password, "device_name": "pytest"},
    )


def test_login_ok_devuelve_token_datos_y_usuario():
    seed_two_users()
    with client() as c:
        resp = _login(c)
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert len(body["token"]) == 64
    assert body["user"] == {"id": 1, "name": "Ana Torres", "email": "ana.torres@example.com"}


def test_login_rechaza_mals_contrasena_como_credenciales_invalidas():
    seed_two_users()
    with client() as c:
        bad_password = _login(c, password="wrong")
        ghost = _login(c, email="ghost@example.com")
    # El mismo mensaje y el mismo status: la respuesta no sirve para
    # enumerar qué emails están dados de alta.
    assert bad_password.status_code == 401
    assert bad_password.json()["detail"] == "Credenciales inválidas"
    assert ghost.status_code == 401
    assert ghost.json()["detail"] == "Credenciales inválidas"


def test_token_repetido_no_nace_del_mismo_hash():
    import hashlib

    seed_two_users()
    with client() as c:
        first = _login(c).json()["token"]
        second = _login(c).json()["token"]
    assert first != second
    assert hashlib.sha256(first.encode()).hexdigest() != hashlib.sha256(
        second.encode()
    ).hexdigest()
