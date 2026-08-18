from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.adaptation import AdaptationRejectResponse
from app.services.adaptation_rejection import (
    AdaptationRejectionConflictError,
    reject_plan_adaptation,
)

router = APIRouter(prefix="/goals", tags=["adaptation"])


@router.post(
    "/{goal_id}/adaptations/{adaptation_id}/reject",
    response_model=AdaptationRejectResponse,
)
def reject_adaptation_endpoint(
    goal_id: UUID,
    adaptation_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdaptationRejectResponse:
    try:
        return reject_plan_adaptation(
            db, goal_id, adaptation_id, current_user.id
        )
    except AdaptationRejectionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject adaptation",
        ) from exc
