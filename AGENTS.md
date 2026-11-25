# AGENTS.md — demo-microservicios (formato FastAPI)

Reglas del repo y patrones asentados hasta el capítulo 10 (JWT stateless).

## Reglas duras

- **Nunca usar comandos de git en este repo.** El dueño maneja el versionado.
- **Nunca tocar `laravel/`**: es una copia temporal del proyecto Laravel (los
  videos de la serie); solo sirve de referencia de contratos y de docs.
- Cada servicio es un proyecto `uv` independiente: instalar y correr SIEMPRE
  desde su directorio (`cd user-service && uv run …`). No hay workspace. Los
  paquetes bajo `packages/` también son proyectos `uv` propios.
- Python ≥3.13 (uv creó venvs con 3.14). `pyproject.toml` por servicio con
  `[dependency-groups] dev = ["pytest"]`.
- **No añadir comentarios de código "por si acaso"**: solo donde explican
  decisiones del diseño (los archivos existentes son la pauta).
- Los docs de la serie son HTML semántico sin SEO/meta/JSON-LD/CSS: doctype,
  charset, `<title>` y `<article>`. Tras escribir un doc largo, VOLVER A LEERLO
  completo y corregir texto espurio.

## Convenciones del proyecto

- Autenticación: dos modos, decididos por **la forma del token** en la
  frontera (`token.count(".") == 2` → JWT; si no → opaco):
  - **Opaco** (default, `TOKEN_MODE=opaque`): TTL de 60 min, solo el hash
    sha256 en `api_tokens`, token crudo una vez en la respuesta.
  - **JWT** (`TOKEN_MODE=jwt`): RS256 firmado por el IdP, TTL 15 min
    (`JWT_TTL_MINUTES`), `iss=user-service`, `jti` para logs. **Cero filas**
    en `api_tokens`. `DELETE /api/tokens` es 204 no-op; el opaco sí borra la fila.
  - La contraseña se guarda con PBKDF2 (stdlib) + `hmac.compare_digest`.
- Claves JWT: generar con `uv run python -m app.jwt_keys` desde `user-service/`;
  privada 0600 y fuera del repo. Rutas por `JWT_PRIVATE_KEY_PATH` /
  `JWT_PUBLIC_KEY_PATH`. `GET /api/jwks.json` público; RP cachea la JWKS 1 h
  (`USER_SERVICE_JWKS_CACHE_TTL`), `leeway=10`, valida `iss`, un solo refetch
  por `kid` desconocido.
  - Con caché fría y el IdP caído → **503** (fallo cerrado, nunca 401).
  - Con caché caliente y el IdP caído → **200** local.
  - En modo JWT no hay `GET /api/user`, así que `X-Request-Id` **no cruza al
    IdP**; el `ContextVar` sigue dando contexto a los logs locales.
- Fechas en las columnas: **datetime naive en UTC** (sqlite no conserva
  tzinfo). Al responder al cliente, `.replace(tzinfo=UTC)` para que salga ISO
  8601 con `Z`. Ver `user-service/app/models.py` (`utcnow`) y
  `app/routes_tokens.py`.
- `user_id` lo pone **el sistema** desde la identidad validada; el payload
  nunca puede inyectarlo. El contrato de la frontera es siempre
  `verify_token(token) -> {"id", "name", "email"}` (en `task-service`, la
  identidad llega como ese dict del IdP).
- Errores de control de acceso: dueño equivocado **403** (la tarea/factura no
  es tuya), no 404. Status inválido **422**. Login: mismo 401 con el mismo
  mensaje para credenciales malas y email inexistente (anti-enumeración).
- Rate limit del login (capítulo 3): limitador propio en
  `user-service/app/rate_limit.py` — ventana deslizante en memoria del
  proceso (cola por clave + `threading.Lock`), dos contadores: **5/min por
  cuenta** (clave `email:sha256|ip`) y **20/min por IP**, cuenta TODOS los
  intentos (no solo los fallidos). Al agotarse: **429** con header
  `Retry-After`. Límites por env `LOGIN_THROTTLE_PER_ACCOUNT/PER_IP/
  DECAY_SECONDS` (5/20/60), ver `user-service/app/config.py`.
  - La dependencia `rate_limit_login(request, payload)` va en
    `dependencies=[...]` de `POST /api/tokens`; el límite es de la ruta, no
    un middleware global.
  - `client_ip(request)` = IP del **socket** (`request.client.host`), nunca
    cabeceras (`X-Forwarded-For` se falsifica a mano). Detrás de proxy en
    producción: uvicorn `--proxy-headers --forwarded-allow-ips <ip del
    proxy>`, jamás `*`.
  - Fixture autouse `limitador_limpio` en `user-service/tests/conftest.py`
    resetea los contadores antes/después de cada test; el seed borra también
    `api_tokens` (la BD `:memory:` con `StaticPool` persiste entre tests).
  - Contadores **por proceso**: reiniciar uvicorn los resetea; con N
    réplicas habría que pasarlos a Redis (quedó abierto en el capítulo 3).
- Logging: `configure_logging()` del paquete de observabilidad en cada
  `main.py`; los mensajes de negocio llevan los campos como JSON en el propio
  mensaje (`json.dumps` con separadores por defecto — lleva espacio, no
  asertar formato exacto): WARNING `Failed login attempt {email, ip,
  account_exists}`, INFO `API token issued/revoked {...}` (en JWT lleva
  `mode:jwt` y `jti`, nunca el token). Nunca la contraseña.

## La frontera (patrón central)

Toda la comunicación inter-servicio vive en el **paquete 2**:
`packages/microservices-user-service-client/src/demo/microservices/user_service_client/`.
Ni `task-service` ni `billing-service` tienen copia local; `deps.py` solo
llama a `verify_token`. Nada más sabe que existe HTTP.

- IdP 401 → 401 local (`Token inválido o expirado`).
- IdP caído/timeout (`httpx2.ConnectError/ConnectTimeout`) → **503** con el
  comando exacto para levantar el servicio faltante.
- IdP responde algo inesperado → **502** (`Respuesta inesperada del
  user-service (HTTP …)`).
- JWT inválido (firma, `iss`, `exp`, `kid`) → **401 sin llamar a la red**.
- JWKS no disponible con caché fría → **503** (`No se pudo obtener la JWKS…`).
- El header malformado (no `Bearer <token>`) se rechaza **sin llamar a la
  red** (`deps.py`); en task-service con `HTTPBearer(auto_error=False)` y
  401 manual, sin `print(token)`.

## Paquetes internos

Dos proyectos `uv` bajo `packages/`, namespace PEP 420 (`demo/` y
`demo/microservices/` **sin `__init__.py`**; solo las hojas lo llevan):

| paquete | import | depende de |
| ------- | ------ | ---------- |
| `microservices-observability` | `demo.microservices.observability` | `starlette` (middleware `X-Request-Id`, health, `configure_logging`, `ContextVar`) |
| `microservices-user-service-client` | `demo.microservices.user_service_client` | paquete de observabilidad + `fastapi`, `httpx2`, `pyjwt`, `cryptography` |

Instalación editable en cada consumidor:
`uv add --editable ../packages/<paquete>` desde el directorio del servicio.
El paquete 2 declara su dependencia del paquete 1 con su propio
`[tool.uv.sources]` (ruta relativa a `packages/`). Config por entorno:
`USER_SERVICE_URL`, `HTTP_TIMEOUT_SECONDS`.

## Stack concreto

- `httpx2` (sucesor de httpx, API idéntica) para llamadas salientes y el
  TestClient de dev; pydantic `EmailStr` necesita `email-validator`.
- SQLAlchemy 2.0 con `sqlalchemy.orm.Mapped/mapped_column`; `create_engine`
  con `check_same_thread: False`, y `StaticPool` para `:memory:` en tests
  (ver `*/app/db.py`).
- Tests: pytest + TestClient **de FastAPI** (starlette), sin servers en pie.
  En `user-service`, BD `:memory:` por `DATABASE_URL` fijada en tests.
  La identidad sale de `app.dependency_overrides`; el IdP se stubbia
  reemplazando `demo.microservices.user_service_client._http_get` (opaco) o
  `…user_service_client.jwks._http_get` (JWKS). Fixture autouse que borra los
  overrides al empezar cada test (nadie arrastra identidad del anterior).
  Claves JWT de tests en memoria o `tmp_path`, nunca del repo.

## Mapeo de servicios

| servicio      | puerto | def                            | puntos de entrada                          |
| ------------- | ------ | ------------------------------ | ------------------------------------------ |
| user-service  | 8000   | PBKDF2 (stdlib) + sha256 token | `/api/tokens`, `/api/user`, `/api/jwks.json` |
| task-service  | 8001   | —                              | `/api/tasks` (CRUD)                        |
| billing-service | 8002 | —                              | `/api/bills` (CRUD)                        |

Seed: `uv run python -m app.seed` desde `user-service/` —
ana.torres@example.com y luis.ramirez@example.com / `password`.

## Comandos útiles

```bash
cd user-service && uv run pytest          # 32 tests
cd task-service && uv run pytest          # 27 tests
cd billing-service && uv run pytest       # 19 tests

cd user-service && uv add 'pyjwt>=2.8' 'cryptography>=42'
cd packages/microservices-user-service-client && uv add 'pyjwt>=2.8' 'cryptography>=42'
cd user-service && uv run python -m app.jwt_keys

uv run uvicorn app.main:app --port 8000   # IdP (desde user-service/)
uv run uvicorn app.main:app --port 8001   # tareas (desde task-service/)
uv run uvicorn app.main:app --port 8002   # facturas (desde billing-service/)
```
