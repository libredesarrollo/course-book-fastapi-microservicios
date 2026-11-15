from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.db import Base, engine
from app.observability import RequestIdMiddleware, configure_logging
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
    description="IdP de la serie: tokens opacos que caducan (capítulo 1).",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(tokens_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Comprobación de vida sin autenticar y sin tocar la base de datos:
    el caso interesante es justo la BD caída, y si el health consultara la
    BD no podría distinguir "vivo pero sin BD" de "muerto"."""
    return {
        "status": "ok",
        "service": "user-service",
        "timestamp": datetime.now(UTC).isoformat(),
    }
