from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import (
    AdaptationDecision,
    AdaptationProposal,
)
from app.models.enums import AdaptationStatus
from app.models.plan_adaptation import PlanAdaptation
from app.services.goal import get_owned_goal


def persist_plan_adaptation(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
    proposal: AdaptationProposal,
) -> PlanAdaptation:
    if proposal.decision is not AdaptationDecision.PROPOSE_CHANGES:
        raise ValueError("Only proposals with changes can be persisted")

    try:
        get_owned_goal(db, goal_id, user_id)
        adaptation = PlanAdaptation(
            goal_id=goal_id,
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
