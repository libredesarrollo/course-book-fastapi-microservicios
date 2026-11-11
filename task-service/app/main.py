from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, engine
from app.routes_tasks import router as tasks_router


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
app.include_router(tasks_router)
