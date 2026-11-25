from contextlib import asynccontextmanager

from fastapi import FastAPI

from demo.microservices.observability import (
    RequestIdMiddleware,
    add_health,
    configure_logging,
)
from app.db import Base, engine
from app.routes_jwks import router as jwks_router
from app.routes_tokens import router as tokens_router

# Sin esto, los INFO (token emitido, revocado) van a ninguna parte: el
# logger de uvicorn solo se trae los WARNING en adelante. Y sin el contexto
# no se puede seguir una petición entre los dos servicios (capítulo 4).
configure_logging("user-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="user-service",
    description="IdP de la serie: tokens opacos (capítulo 1) o JWT RS256 (capítulo 10).",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(tokens_router)
app.include_router(jwks_router)
add_health(app, "user-service")
