from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
) -> GoalResponse:
    goal = create_goal(db, data)

    return GoalResponse.model_validate(goal)
