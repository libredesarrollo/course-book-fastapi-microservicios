import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import STATUS_PENDING, Bill
from app.schemas import BillCreate, BillOut, BillUpdate, normalize_status

router = APIRouter(prefix="/api", tags=["bills"])

log = logging.getLogger("billing-service")


def find_owned(bill_id: int, current_user: dict[str, Any], db: Session) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if bill.user_id != current_user["id"]:
        # El 403 va antes que cualquier error interno: no existe para ti.
        raise HTTPException(status_code=403, detail="No es tu factura")
    return bill


@router.post("/bills", response_model=BillOut, status_code=201)
def create_bill(
    payload: BillCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Bill:
    bill = Bill(
        task_title=payload.task_title,
        task_id=payload.task_id,
        amount=payload.amount,
        status=normalize_status(payload.status, STATUS_PENDING),
        # El dueño lo pone el sistema: el cliente no manda user_id.
        user_id=current_user["id"],
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/bills", response_model=list[BillOut])
def list_bills(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Bill]:
    return list(
        db.query(Bill)
        .filter(Bill.user_id == current_user["id"])
        .order_by(Bill.id.desc())
        .all()
    )


@router.get("/bills/{bill_id}", response_model=BillOut)
def show_bill(
    bill_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Bill:
    return find_owned(bill_id, current_user, db)


@router.put("/bills/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: int,
    payload: BillUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Bill:
    bill = find_owned(bill_id, current_user, db)
    if payload.task_title is not None:
        bill.task_title = payload.task_title
    if payload.amount is not None:
        bill.amount = payload.amount
    if payload.task_id is not None:
        bill.task_id = payload.task_id
    bill.status = normalize_status(payload.status, bill.status)
    db.commit()
    db.refresh(bill)
    return bill


@router.delete("/bills/{bill_id}", status_code=204)
def delete_bill(
    bill_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    bill = find_owned(bill_id, current_user, db)
    db.query(Bill).filter(Bill.id == bill.id).delete()
    db.commit()
