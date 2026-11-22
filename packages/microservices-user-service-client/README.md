# microservices-user-service-client

Paquete interno de la serie `demo-microservicios` (versión FastAPI):
la frontera de red con el IdP (`user-service`), compartida por los
servicios que validan tokens.

## Qué contiene

- `verify_token(token)`: pregunta al IdP (`GET /api/user` con el token
  opaco) y devuelve `{"id", "name", "email"}` o lanza `HTTPException` ya
  mapeada: `401` identidad inválida, `503` IdP caído (con el comando para
  levantarlo), `502` respuesta inesperada.
- `LOGGER_NAME`: el nombre del logger de la frontera
  (`"user-service-client"`). Cada servicio lo pasa a `configure_logging()`
  para que los warnings lleven el `request_id`.
- Propagación del correlation ID: lee el `ContextVar` del paquete
  `microservices-observability` y manda `X-Request-Id` al IdP.

## Consumo

```toml
# pyproject.toml del servicio
dependencies = ["microservices-user-service-client"]

[tool.uv.sources]
microservices-user-service-client = { path = "../packages/microservices-user-service-client", editable = true }
```

Este paquete **depende a su vez** de `microservices-observability`
(necesita el `ContextVar` del `request_id`); su `pyproject.toml` declara
esa dependencia con su propio bloque `[tool.uv.sources]`.

## Configuración (por entorno)

- `USER_SERVICE_URL` (default `http://127.0.0.1:8000`)
- `HTTP_TIMEOUT_SECONDS` (default `2`)

## Nació con el tercer servicio

Con task-service solo, este archivo vivía en `task-service/app/`. Cuando
apareció billing-service hubo dos copias byte a byte, y las decisiones de
la frontera (401/503/502, traza) pasaron a poder divergir. El paquete es la
única copia desde el capítulo 6.
