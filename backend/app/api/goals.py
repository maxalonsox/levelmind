from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.goal import GoalCreate, GoalResponse
from app.services.goal import create_goal

router = APIRouter(
    prefix="/goals",
    tags=["goals"],
)


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
