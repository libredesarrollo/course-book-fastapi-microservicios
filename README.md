# demo-microservicios (formato FastAPI)

El mismo proyecto de la serie, escrito en FastAPI. Capítulo 1: dos servicios,
tokens opacos y la frontera HTTP en un solo sitio.

## Servicios

| servicio      | puerto | qué hace                                                        |
| ------------- | ------ | --------------------------------------------------------------- |
| user-service  | 8000   | IdP: login por email/password, tokens opacos con TTL de 60 min   |
| task-service  | 8001   | CRUD de tareas por usuario; confía la identidad al IdP por HTTP  |

Cada servicio es un proyecto `uv` independiente (su propio `pyproject.toml` y
`.venv`), sin workspace. SQLite: `database.sqlite` en el directorio de cada
servicio (en los tests, `:memory:`).

## Cómo levantar

```bash
# Terminal 1 — IdP
cd user-service && uv run uvicorn app.main:app --port 8000

# Terminal 2 — tareas
cd task-service && uv run uvicorn app.main:app --port 8001
```

Seed: `cd user-service && uv run python -m app.seed`
(ana.torres@example.com y luis.ramirez@example.com / password).

## Flujo de una sesión

```bash
# login -> 201 {"token", "token_type": "Bearer", "expires_at", "user"}
curl -X POST http://127.0.0.1:8000/api/tokens \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana.torres@example.com", "password": "password"}'

# crear tarea (el dueño lo pone el sistema, no el payload, aunque lo mandes)
curl -X POST http://127.0.0.1:8001/api/tasks \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Comprar pan"}'

# cerrar sesión: revocar el token -> 204 -> el token vale nada en los dos
curl -X DELETE http://127.0.0.1:8000/api/tokens -H "Authorization: Bearer $TOKEN"
```

## Contratos

- `POST /api/tokens` — 201 con el token (el crudo sale una vez, en la BD
  queda solo su hash sha256); credenciales malas o email fantasma: mismo 401
  `Credenciales inválidas` (anti-enumeración).
- `GET /api/user` — 200 `{id, name, email}` o 401.
- `DELETE /api/tokens` — 204; revocación real: la fila se borra y el token
  muere en todos los servicios al instante.
- `GET/POST/PUT/DELETE /api/tasks` — 201/200/204; tarea ajena 403,
  inexistente 404, `status` fuera de `pending|completed` 422.

## La frontera (la lección del capítulo)

Toda la llamada al IdP vive en `task-service/app/user_service_client.py`.
El resto del servicio recibe el usuario como si fuera local.

- IdP dice 401 → task-service responde 401 (identidad inválida).
- IdP caído o timeout → **503** con instrucciones de cómo levantarlo
  (fallo de infraestructura, no del cliente).
- IdP responde algo raro → **502** (respuesta inesperada).

## Docs de la serie

- `docs/01-estructura-base.html` — capítulo 1: dos servicios, tokens opacos
  y la frontera HTTP (deck navegable con ← → y version imprimible).

## Tests

```bash
cd user-service && uv run pytest   # 7 tests, TestClient + :memory:
cd task-service && uv run pytest   # 11 tests, dependency_overrides + stubs
```

Los tests no levantan servidores ni tocan la red real: la identidad sale de
overrides, y el cliente del IdP se sustituye por stubs.
