from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import STATUS_PENDING, Task, STATUSES
from app.schemas import TaskCreate, TaskOut, TaskUpdate, normalize_status
from typing import Any

router = APIRouter(prefix="/api", tags=["tasks"])


def find_owned(task_id: int, current_user: dict[str, Any], db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if task.user_id != current_user["id"]:
        # El 403 va antes que cualquier error interno: no existe para ti.
        raise HTTPException(status_code=403, detail="No es tu tarea")
    return task


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = Task(
        title=payload.title,
        status=normalize_status(payload.status, STATUS_PENDING),
        # El dueño lo pone el sistema, el cliente no lo manda (Miguel no
        # confiando en el payload: user_id de la identidad validada).
        user_id=current_user["id"],
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Task]:
    return list(
        db.query(Task)
        .filter(Task.user_id == current_user["id"])
        .order_by(Task.id.desc())
        .all()
    )


@router.get("/tasks/{task_id}", response_model=TaskOut)
def show_task(
    task_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    return find_owned(task_id, current_user, db)


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Task:
    task = find_owned(task_id, current_user, db)
    if payload.title is not None:
        task.title = payload.title
    task.status = normalize_status(payload.status, task.status)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    task = find_owned(task_id, current_user, db)
    db.query(Task).filter(Task.id == task.id).delete()
    db.commit()
