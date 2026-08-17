from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import (
    AdaptationDecision,
    AdaptationProposal,
)
from app.models.enums import AdaptationStatus
from app.models.plan_adaptation import PlanAdaptation
from app.services.adaptation import (
    validate_adaptation_targets_against_outline,
)
from app.services.adaptation_context import build_current_plan_outline
from app.services.goal import get_owned_goal
from app.services.plan_revision import get_current_plan_revision


class PlanRevisionConflictError(Exception):
    """Raised when an adaptation no longer matches the current revision."""


def persist_plan_adaptation(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
    proposal: AdaptationProposal,
    base_revision_id: UUID,
) -> PlanAdaptation:
    if proposal.decision is not AdaptationDecision.PROPOSE_CHANGES:
        raise ValueError("Only proposals with changes can be persisted")

    try:
        get_owned_goal(db, goal_id, user_id, for_update=True)
        current_revision = get_current_plan_revision(
            db, goal_id, for_update=True
        )
        if (
            current_revision is None
            or current_revision.id != base_revision_id
        ):
            raise PlanRevisionConflictError
        validate_adaptation_targets_against_outline(
            proposal, build_current_plan_outline(db, goal_id)
        )
        adaptation = PlanAdaptation(
            goal_id=goal_id,
            base_revision_id=current_revision.id,
            proposal=proposal.model_dump(mode="json"),
            status=AdaptationStatus.PENDING,
        )
        db.add(adaptation)
        db.commit()
        db.refresh(adaptation)
        return adaptation
    except Exception:
        db.rollback()
        raise
