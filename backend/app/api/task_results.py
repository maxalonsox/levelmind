from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.task import (
    TaskResponse,
    TaskResultCreate,
    TaskResultResponse,
    TaskUpdate,
)
from app.services.task import (
    TaskAlreadyResolvedError,
    TaskNotEditableError,
    resolve_task,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task_endpoint(
    task_id: UUID,
    data: TaskUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    try:
        return update_task(db, task_id, data, current_user.id)
    except TaskNotEditableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending Tasks can be edited",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Task",
        ) from exc


@router.post("/{task_id}/result", response_model=TaskResultResponse)
def resolve_task_endpoint(
    task_id: UUID,
    data: TaskResultCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResultResponse:
    try:
        return resolve_task(db, task_id, data, current_user.id)
    except TaskAlreadyResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already has a different terminal result",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record Task result",
        ) from exc
