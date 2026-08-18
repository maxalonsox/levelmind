from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.goal import GoalCreate, GoalResponse
from app.services.goal import create_goal, delete_owned_goal, get_active_goal

router = APIRouter(
    prefix="/goals",
    tags=["goals"],
)


@router.get("/active", response_model=GoalResponse)
def get_active_goal_endpoint(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalResponse:
    return GoalResponse.model_validate(get_active_goal(db, current_user.id))


@router.post(
    "",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_goal_endpoint(
    data: GoalCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalResponse:
    goal = create_goal(db, data, current_user.id)

    return GoalResponse.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_endpoint(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    delete_owned_goal(db, goal_id, current_user.id)
