from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.plan import GoalPlanResponse
from app.services.plan import get_goal_plan

router = APIRouter(prefix="/goals", tags=["planning"])


@router.get("/{goal_id}/plan", response_model=GoalPlanResponse)
def get_goal_plan_endpoint(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalPlanResponse:
    return get_goal_plan(db, goal_id, current_user.id)
