from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, engine
from app.routes_tokens import router as tokens_router


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
app.include_router(tokens_router)
