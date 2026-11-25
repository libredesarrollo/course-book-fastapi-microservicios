# demo-microservicios (formato FastAPI)

El mismo proyecto de la serie, escrito en FastAPI. Tres servicios, dos paquetes
internos, tokens opacos o JWT RS256 (stateless) según `TOKEN_MODE`.

## Servicios

| servicio       | puerto | qué hace                                                       |
| -------------- | ------ | -------------------------------------------------------------- |
| user-service   | 8000   | IdP: login email/password, token opaco (60 min) o JWT (15 min)  |
| task-service   | 8001   | CRUD de tareas por usuario; identidad validada en la frontera  |
| billing-service | 8002  | CRUD de facturas por usuario; mismo paquete de frontera        |

Cada servicio es un proyecto `uv` independiente (su propio `pyproject.toml` y
`.venv`), sin workspace. SQLite: `database.sqlite` en el directorio de cada
servicio (en los tests, `:memory:`).

## Paquetes internos

| paquete | import | qué da |
| ------- | ------ | ------ |
| `microservices-observability` | `demo.microservices.observability` | `X-Request-Id`, health, logs con traza |
| `microservices-user-service-client` | `demo.microservices.user_service_client` | `verify_token` para opaco y JWT, JWKS cacheada |

Se instalan en modo editable: `uv add --editable ../packages/<paquete>` desde
cada servicio. El paquete 2 depende del paquete 1 (comparte el `ContextVar` del
`request_id`) y también de `pyjwt` y `cryptography`.

## Cómo levantar

```bash
# IdP (opaco por defecto; añade TOKEN_MODE=jwt para JWT)
cd user-service && uv run python -m app.jwt_keys        # solo en modo JWT
cd user-service && uv run uvicorn app.main:app --port 8000

# Otros dos servicios, cada uno en su directorio
cd task-service && uv run uvicorn app.main:app --port 8001
cd billing-service && uv run uvicorn app.main:app --port 8002
```

Seed: `cd user-service && uv run python -m app.seed`
(ana.torres@example.com y luis.ramirez@example.com / password).

## Flujo de una sesión

```bash
# login -> 201 {"token", "token_type": "Bearer", "expires_at", "user"}
# con TOKEN_MODE=jwt el token tiene 3 segmentos; con opaque, 64 chars
curl -X POST http://127.0.0.1:8000/api/tokens \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana.torres@example.com", "password": "password"}'

# el MISMO token vale para task y billing (el dueño lo pone el sistema)
curl -X POST http://127.0.0.1:8001/api/tasks \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d '{"title": "Comprar pan"}'
curl -X POST http://127.0.0.1:8002/api/bills \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d '{"task_title": "Informe", "amount": 10.5}'

# cerrar sesión -> 204
# opaco: la fila se borra y el token muere al instante
# JWT: no-op validado; el token sigue vivo hasta exp (15 min)
curl -X DELETE http://127.0.0.1:8000/api/tokens -H "Authorization: Bearer $TOKEN"
```

## Contratos

- `POST /api/tokens` — 201 con el token (crudo una vez; en opaco solo se
  guarda su hash sha256); credenciales malas o email fantasma: mismo 401
  `Credenciales inválidas` (anti-enumeración). Rate limit: 5/min por cuenta
  (email+IP) y 20/min por IP, cuenta todos los intentos; al agotarse, 429 con
  header `Retry-After`.
- `GET /api/user` — 200 `{id, name, email}` o 401. Acepta opaco y JWT.
- `GET /api/jwks.json` — público, clave RSA pública del IdP (`kid`, `n`, `e`).
- `DELETE /api/tokens` — 204; revoca de verdad en opaco, no-op en JWT.
- `GET/POST/PUT/DELETE /api/tasks` — 201/200/204; ajeno 403, inexistente 404,
  `status` fuera de `pending|completed` 422.
- `GET/POST/PUT/DELETE /api/bills` — igual, con `status` `pending|paid` y
  `amount > 0`.

## La frontera (la lección de los capítulos 5 y 6)

Toda la comunicación con el IdP vive en
`packages/microservices-user-service-client/`. Ni task-service ni
billing-service tienen copia local; sus `deps.py` solo llaman a `verify_token`.

- JWT: firma RS256 verificada con JWKS cacheada (1 h), sin salto de red por
  petición. Con el IdP caído y caché caliente → **200**; con caché fría → 503.
- Opaco: IdP 401 → 401 local; IdP caído → **503** con cómo levantarlo;
  respuesta rara → **502**.
- JWT inválido → 401 **sin ir a la red**. Header malformado → 401 en
  `deps.py`, también sin red.

## Docs de la serie

- `docs/01-estructura-base.html` — capítulo 1: dos servicios y tokens opacos.
- `docs/02-flujo-autenticacion.html` — capítulo 2: el flujo en detalle.
- `docs/03-rate-limit.html` — capítulo 3: el limitador del login.
- `docs/05-modulos-composer.html` — capítulo 5: observabilidad y paquetes UV.
- `docs/06-tercer-servicio.html` — capítulo 6: billing-service y el paquete 2.
- `docs/10-jwt-stateless.html` — capítulo 10: JWT RS256, JWKS y verificación
  local, con todos los comandos `uv` usados.

El 08 (SSO con formularios/cookies) no se portó: FastAPI no tiene sesiones web
y la identidad ya vivía solo en el IdP. El 09 (resiliencia) queda para después:
los reintentos y el circuit breaker protegen el camino opaco que permanece.

## Tests

```bash
cd user-service && uv run pytest     # 32 tests
cd task-service && uv run pytest     # 27 tests
cd billing-service && uv run pytest  # 19 tests
```

Los tests no levantan servidores ni tocan la red real: la identidad sale de
overrides, y la frontera se sustituye por stubs (`_http_get` para el opaco,
`jwks._http_get` para la JWKS). Las claves JWT se generan en memoria o en
`tmp_path`.
