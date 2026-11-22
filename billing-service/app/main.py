from contextlib import asynccontextmanager

from fastapi import FastAPI

from demo.microservices.observability import (
    RequestIdMiddleware,
    add_health,
    configure_logging,
)
from demo.microservices.user_service_client import LOGGER_NAME
from app.db import Base, engine
from app.routes_bills import router as bills_router

# INFO visible y request_id en cada línea: aquí nacen los warnings de la
# frontera (paquete microservices-user-service-client) y deben salir con
# su traza (capítulo 4).
configure_logging("billing-service", LOGGER_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="billing-service",
    description="Facturas por usuario, autenticadas vía el IdP (capítulo 6).",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(bills_router)
add_health(app, "billing-service")
