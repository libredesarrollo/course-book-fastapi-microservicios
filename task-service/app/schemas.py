from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import STATUSES


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


def normalize_status(value: str | None, default: str) -> str:
    if value is None:
        return default
    if value not in STATUSES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"status debe ser uno de: {', '.join(STATUSES)}",
        )
    return value
