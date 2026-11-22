from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUSES = (STATUS_PENDING, STATUS_PAID)


def utcnow() -> datetime:
    # Naive en UTC: sqlite no conserva tzinfo.
    return datetime.now(UTC).replace(tzinfo=None)


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    # De qué tarea nace la factura; None si se creó a mano.
    task_id: Mapped[int | None]
    task_title: Mapped[str] = mapped_column(Text)
    amount: Mapped[float]
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
