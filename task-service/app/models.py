from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUSES = (STATUS_PENDING, STATUS_COMPLETED)


def utcnow() -> datetime:
    # Naive en UTC: sqlite no conserva tzinfo.
    return datetime.now(UTC).replace(tzinfo=None)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
