from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.generated_plan import GeneratedPlan, PersistedPlan
from app.services.generated_plan import (
    GoalAlreadyHasPlanError,
    persist_generated_plan,
)

router = APIRouter(prefix="/goals", tags=["planning"])


@router.post(
    "/{goal_id}/plan/accept",
    response_model=PersistedPlan,
    status_code=status.HTTP_201_CREATED,
)
def accept_goal_plan(
    goal_id: UUID,
    generated_plan: GeneratedPlan,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PersistedPlan:
    try:
        return persist_generated_plan(
            db,
            goal_id,
            current_user.id,
            generated_plan,
        )
    except GoalAlreadyHasPlanError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Goal already has a persisted plan",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist accepted plan",
        ) from exc
