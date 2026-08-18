from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AdaptationStatus
from app.models.plan_adaptation import PlanAdaptation
from app.schemas.adaptation import AdaptationRejectResponse
from app.services.goal import get_owned_goal


class AdaptationRejectionConflictError(Exception):
    """Raised when a persisted adaptation can no longer be rejected."""


def reject_plan_adaptation(
    db: Session,
    goal_id: UUID,
    adaptation_id: UUID,
    user_id: UUID,
) -> AdaptationRejectResponse:
    try:
        get_owned_goal(db, goal_id, user_id)
        adaptation = db.scalar(
            select(PlanAdaptation)
            .where(
                PlanAdaptation.id == adaptation_id,
                PlanAdaptation.goal_id == goal_id,
            )
            .with_for_update()
        )
        if adaptation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Adaptation not found",
            )
        if AdaptationStatus(adaptation.status) is not AdaptationStatus.PENDING:
            raise AdaptationRejectionConflictError(
                "Adaptation has already been reviewed"
            )

        reviewed_at = datetime.now(UTC)
        adaptation.status = AdaptationStatus.REJECTED
        adaptation.reviewed_at = reviewed_at
        db.flush()
        response = AdaptationRejectResponse(
            adaptation_id=adaptation.id,
            status=AdaptationStatus.REJECTED,
            reviewed_at=reviewed_at,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
