from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.task import TaskCreate, TaskResponse
from app.services.task import create_task, list_tasks

router = APIRouter(prefix="/missions/{mission_id}/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(
    mission_id: UUID,
    data: TaskCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    task = create_task(db, data, mission_id, current_user.id)
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskResponse])
def list_tasks_endpoint(
    mission_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TaskResponse]:
    return [
        TaskResponse.model_validate(task)
        for task in list_tasks(db, mission_id, current_user.id)
    ]
