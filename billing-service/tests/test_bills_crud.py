from tests.conftest import client_for, seed_bills


def test_crear_201_con_dueno_del_sistema_no_del_payload():
    seed_bills()
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.post(
            "/api/bills",
            json={"task_title": "Comprar pan", "amount": 10.0, "user_id": 99},
        )
    assert resp.status_code == 201
    bill = resp.json()
    assert bill["task_title"] == "Comprar pan"
    assert bill["amount"] == 10.0
    assert bill["status"] == "pending"
    # El dueño lo pone el sistema desde la identidad validada, no el payload:
    assert bill["user_id"] == 7


def test_crear_monto_negativo_es_422():
    seed_bills()
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.post("/api/bills", json={"task_title": "X", "amount": -1})
    assert resp.status_code == 422


def test_listar_solo_las_tuyas():
    seed_bills((7, "Mía", 10.0, "pending"), (8, "Ajena", 10.0, "pending"), (7, "Otra mía", 5.0, "paid"))
    anita = {"id": 7, "name": "Ana", "email": "ana@example.com"}
    luis = {"id": 8, "name": "Luis", "email": "luis@example.com"}
    with client_for(anita) as c:
        resp = c.get("/api/bills")
    with client_for(luis) as c2:
        resp_luis = c2.get("/api/bills")
    titles = [b["task_title"] for b in resp.json()]
    assert titles == ["Otra mía", "Mía"]  # desc por id, sin la de Luis
    assert [b["task_title"] for b in resp_luis.json()] == ["Ajena"]


def test_ver_propia_200_ajena_403_inexistente_404():
    seed_bills((7, "Mía", 10.0, "pending"), (8, "Ajena", 10.0, "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        mía = c.get("/api/bills/1")
        ajena = c.get("/api/bills/2")
        fuera = c.get("/api/bills/999")
    assert mía.status_code == 200 and mía.json()["id"] == 1
    assert ajena.status_code == 403
    assert fuera.status_code == 404


def test_actualizar_y_marcar_pagada_200_invalido_422():
    seed_bills((7, "Mía", 10.0, "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.put("/api/bills/1", json={"status": "paid", "amount": 12.5})
        raro = c.put("/api/bills/1", json={"status": "fly"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    assert resp.json()["amount"] == 12.5
    assert raro.status_code == 422


def test_actualizar_ajena_403():
    seed_bills((8, "Ajena", 10.0, "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.put("/api/bills/1", json={"status": "paid"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "No es tu factura"


def test_borrar_204_y_despues_404_ajena_403():
    seed_bills((7, "Mía", 10.0, "pending"), (8, "Ajena", 10.0, "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        ok = c.delete("/api/bills/1")
        ya_fuera = c.delete("/api/bills/1")
        hack = c.delete("/api/bills/2")
    assert ok.status_code == 204
    assert ya_fuera.status_code == 404
    assert hack.status_code == 403
