from tests.conftest import client_for, seed_tasks


def test_crear_201_con_dueno_del_sistema_no_del_payload():
    seed_tasks()
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.post(
            "/api/tasks",
            json={"title": "Comprar pan", "user_id": 99},
        )
    assert resp.status_code == 201
    task = resp.json()
    assert task["title"] == "Comprar pan"
    # El dueño lo pone el sistema desde la identidad validada, no el payload:
    assert task["user_id"] == 7


def test_listar_solo_las_tuyas():
    seed_tasks((7, "Mía", "pending"), (8, "Ajena", "pending"), (7, "Otra mía", "completed"))
    anita = {"id": 7, "name": "Ana", "email": "ana@example.com"}
    luis = {"id": 8, "name": "Luis", "email": "luis@example.com"}
    with client_for(anita) as c:
        resp = c.get("/api/tasks")
    with client_for(luis) as c2:
        resp_luis = c2.get("/api/tasks")
    titles = [t["title"] for t in resp.json()]
    assert titles == ["Otra mía", "Mía"]  # desc por id, sin la de Luis
    assert [t["title"] for t in resp_luis.json()] == ["Ajena"]


def test_ver_propia_200_ajena_403_inexistente_404():
    seed_tasks((7, "Mía", "pending"), (8, "Ajena", "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        mía = c.get("/api/tasks/1")
        ajena = c.get("/api/tasks/2")
        fuera = c.get("/api/tasks/999")
    assert mía.status_code == 200 and mía.json()["id"] == 1
    assert ajena.status_code == 403
    assert fuera.status_code == 404


def test_actualizar_titulo_y_status_200_invalido_422():
    seed_tasks((7, "Mía", "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.put("/api/tasks/1", json={"title": "Escribir el informe", "status": "completed"})
        raro = c.put("/api/tasks/1", json={"status": "fly"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Escribir el informe"
    assert resp.json()["status"] == "completed"
    assert raro.status_code == 422


def test_actualizar_ajena_403():
    seed_tasks((8, "Ajena", "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        resp = c.put("/api/tasks/1", json={"title": "hack"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "No es tu tarea"


def test_borrar_204_y_despues_404_ajena_403():
    seed_tasks((7, "Mía", "pending"), (8, "Ajena", "pending"))
    with client_for({"id": 7, "name": "Ana", "email": "ana@example.com"}) as c:
        ok = c.delete("/api/tasks/1")
        ya_fuera = c.delete("/api/tasks/1")
        hack = c.delete("/api/tasks/2")
    assert ok.status_code == 204
    assert ya_fuera.status_code == 404
    assert hack.status_code == 403
