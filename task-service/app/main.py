from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.db import Base, engine
from app.observability import RequestIdMiddleware, configure_logging
from app.routes_tasks import router as tasks_router

# INFO visible y request_id en cada línea: aquí nacen los warnings de la
# frontera (app/user_service_client.py) y deben salir con su traza
# (capítulo 4).
configure_logging("task-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="task-service",
    description="Tareas por usuario, autenticadas vía el IdP (capítulo 1).",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Comprobación de vida sin autenticar y sin tocar la base de datos:
    el caso interesante es justo la BD caída, y si el health consultara la
    BD no podría distinguir "vivo pero sin BD" de "muerto"."""
    return {
        "status": "ok",
        "service": "task-service",
        "timestamp": datetime.now(UTC).isoformat(),
    }
