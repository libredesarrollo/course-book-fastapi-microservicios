# AGENTS.md — demo-microservicios (formato FastAPI)

Reglas del repo y patrones asentados hasta el capítulo 1.

## Reglas duras

- **Nunca usar comandos de git en este repo.** El dueño maneja el versionado.
- **Nunca tocar `laravel/`**: es una copia temporal del proyecto Laravel (los
  videos de la serie); solo sirve de referencia de contratos y de docs.
- Cada servicio es un proyecto `uv` independiente: instalar y correr SIEMPRE
  desde su directorio (`cd user-service && uv run …`). No hay workspace.
- Python ≥3.13 (uv creó venvs con 3.14). `pyproject.toml` por servicio con
  `[dependency-groups] dev = ["pytest"]`.
- **No añadir comentarios de código "por si acaso"**: solo donde explican
  decisiones del diseño (los archivos existentes son la pauta).

## Convenciones del proyecto

- Autenticación: **tokens opacos** con TTL de 60 min. El servicio que emite
  guarda solo el hash sha256; el token crudo sale una vez en la respuesta.
  La contraseña se guarda con PBKDF2 (stdlib) + `hmac.compare_digest`.
- Fechas en las columnas: **datetime naive en UTC** (sqlite no conserva
  tzinfo). Al responder al cliente, `.replace(tzinfo=UTC)` para que salga ISO
  8601 con `Z`. Ver `user-service/app/models.py` (`utcnow`) y
  `app/routes_tokens.py`.
- `user_id` lo pone **el sistema** desde la identidad validada; el payload
  nunca puede inyectarlo. Excepción: en `task-service`, la identidad llega
  como dict del IdP (`{"id", "name", "email"}`).
- Errores de control de acceso: dueño equivocado **403** (la tarea no es
  tuya), no 404. Status inválido **422**. Login: mismo 401 con el mismo
  mensaje para credenciales malas y email inexistente (anti-enumeración).

## La frontera (patrón central)

Toda la comunicación inter-servicio vive en un solo archivo:
`task-service/app/user_service_client.py`. Nada más sabe que existe HTTP.

- IdP 401 → 401 local (`Token inválido o expirado`).
- IdP caído/timeout (`httpx2.ConnectError/ConnectTimeout`) → **503** con el
  comando exacto para levantar el servicio faltante.
- IdP responde algo inesperado → **502** (`Respuesta inesperada del
  user-service (HTTP …)`).
- El header malformado (no `Bearer <token>`) se rechaza **sin llamar a la
  red** (`app/deps.py`).

## Stack concreto

- `httpx2` (sucesor de httpx, API idéntica) para llamadas salientes y el
  TestClient de dev; pydantic `EmailStr` necesita `email-validator`.
- SQLAlchemy 2.0 con `sqlalchemy.orm.Mapped/mapped_column`; `create_engine`
  con `check_same_thread: False`, y `StaticPool` para `:memory:` en tests
  (ver `*/app/db.py`).
- Tests: pytest + TestClient **de FastAPI** (starlette), sin servers en pie.
  En `user-service`, BD `:memory:` por `DATABASE_URL` fijada en tests.
  En `task-service`, la identidad sale de `app.dependency_overrides` y el
  IdP se stubbia reemplazando `app.user_service_client._http_get`. Fixture
  autouse que borra los overrides al empezar cada test (nadie arrastra
  identidad del anterior).

## Mapeo de servicios

| servicio     | puerto | bcrypt/def                     | puntos de entrada             |
| ------------ | ------ | ------------------------------ | ----------------------------- |
| user-service | 8000   | PBKDF2 (stdlib) + sha256 token | `/api/tokens`, `/api/user`    |
| task-service | 8001   | —                              | `/api/tasks` (CRUD)           |

Seed: `uv run python -m app.seed` desde `user-service/` —
ana.torres@example.com y luis.ramirez@example.com / `password`.

## Comandos útiles

```bash
cd user-service && uv run pytest          # 7 tests
cd task-service && uv run pytest          # 11 tests
uv run uvicorn app.main:app --port 8000   # IdP (desde user-service/)
uv run uvicorn app.main:app --port 8001   # tareas (desde task-service/)
```
