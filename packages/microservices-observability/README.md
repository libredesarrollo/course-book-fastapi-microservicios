# microservices-observability

Paquete interno de la serie `demo-microservicios` (versión FastAPI):
correlation ID (`X-Request-Id`), health check y logs con contexto para los
microservicios.

## Qué contiene

- `RequestIdMiddleware`: respeta el `X-Request-Id` entrante o genera un
  UUID v4; siempre lo devuelve en la respuesta. El ID queda en un
  `ContextVar` al alcance de cualquier código de la petición.
- `request_id`: el `ContextVar` compartido.
- `RequestIdFilter` / `RequestIdFormatter` / `configure_logging`:
  el `request_id` en cada línea de log sin pasarlo a mano.
- `add_health(app, service)`: publica `GET /health`, payload estático,
  sin base de datos ni autenticación.

## Consumo

Cada servicio lo declara como dependencia editable por ruta (el
equivalente Python de los repositorios `path` de Composer), de modo que un
cambio aquí se ve al instante en los dos servicios:

```toml
# pyproject.toml del servicio
dependencies = ["microservices-observability"]

[tool.uv.sources]
microservices-observability = { path = "../packages/microservices-observability", editable = true }
```

La aplicación decide qué se aplica y dónde: el middleware se monta con
`app.add_middleware(RequestIdMiddleware)`, el health con
`add_health(app, "user-service")`, y `configure_logging` recibe los nombres
de los loggers de negocio de cada servicio. El paquete no toma esas
decisiones por la aplicación.

## Dependencias

Solo `starlette`: el paquete no declara `fastapi` para no obligar a
instalar el framework completo; los consumidores ya lo tienen.
