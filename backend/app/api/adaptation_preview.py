from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationDecision,
)
from app.ai.adaptation.errors import (
    AdaptationError,
    AdaptationProviderTimeoutError,
)
from app.ai.adaptation.openai_compatible import (
    OpenAICompatibleAdaptationProvider,
)
from app.ai.orchestration.adaptive_reasoning import (
    AdaptiveReasoningOrchestrator,
)
from app.ai.errors import AIConfigurationError
from app.ai.evaluation.contracts import EvaluationContext, EvaluationResult
from app.ai.evaluation.errors import (
    EvaluationError,
    EvaluationProviderTimeoutError,
)
from app.api.evaluation_preview import get_evaluation_provider_factory
from app.auth import AuthenticatedUser, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.adaptation import AdaptationPreviewResponse
from app.services.adaptation import (
    AdaptationProviderFactory,
    AdaptationService,
    build_no_change_proposal,
)
from app.services.adaptation_context import build_adaptation_context
from app.services.evaluation import (
    EvaluationProviderFactory,
    EvaluationService,
)
from app.services.evaluation_context import build_evaluation_context
from app.services.plan_adaptation import (
    PlanRevisionConflictError,
    persist_plan_adaptation,
)
from app.services.plan_revision import ensure_current_plan_revision

router = APIRouter(prefix="/goals", tags=["adaptation"])


def get_adaptation_provider_factory() -> AdaptationProviderFactory:
    return lambda: OpenAICompatibleAdaptationProvider(get_settings())


@router.post(
    "/{goal_id}/adaptation/preview",
    response_model=AdaptationPreviewResponse,
)
async def preview_goal_adaptation(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    evaluation_provider_factory: Annotated[
        EvaluationProviderFactory,
        Depends(get_evaluation_provider_factory),
    ],
    adaptation_provider_factory: Annotated[
        AdaptationProviderFactory,
        Depends(get_adaptation_provider_factory),
    ],
) -> AdaptationPreviewResponse:
    base_revision_id: UUID | None = None

    def evaluation_context_builder(
        requested_goal_id: UUID,
        user_id: UUID,
    ) -> EvaluationContext:
        return build_evaluation_context(db, requested_goal_id, user_id)

    def adaptation_context_builder(
        requested_goal_id: UUID,
        user_id: UUID,
        evaluation_context: EvaluationContext,
        evaluation: EvaluationResult,
    ) -> AdaptationContext:
        nonlocal base_revision_id
        base_revision = ensure_current_plan_revision(
            db, requested_goal_id, user_id
        )
        base_revision_id = base_revision.id
        return build_adaptation_context(
            db,
            requested_goal_id,
            user_id,
            evaluation_context,
            evaluation,
        )

    orchestrator = AdaptiveReasoningOrchestrator(
        evaluation_service=EvaluationService(evaluation_provider_factory),
        adaptation_service=AdaptationService(adaptation_provider_factory),
        build_evaluation_context=evaluation_context_builder,
        build_adaptation_context=adaptation_context_builder,
    )
    try:
        graph_result = await orchestrator.run(
            user_id=current_user.id,
            goal_id=goal_id,
        )
        evaluation = graph_result["evaluation"]
        proposal = graph_result.get("adaptation") or build_no_change_proposal(
            evaluation
        )
        adaptation = None
        if proposal.decision is AdaptationDecision.PROPOSE_CHANGES:
            if base_revision_id is None:
                raise RuntimeError(
                    "Adaptation ran without a base Plan revision"
                )
            adaptation = persist_plan_adaptation(
                db,
                goal_id,
                current_user.id,
                proposal,
                base_revision_id,
            )
        return AdaptationPreviewResponse(
            **proposal.model_dump(),
            needs_adaptation=evaluation.needs_adaptation,
            adaptation=adaptation,
        )
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except EvaluationProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Evaluation provider timed out",
        ) from exc
    except AdaptationProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Adaptation provider timed out",
        ) from exc
    except EvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Evaluation provider returned an invalid response",
        ) from exc
    except AdaptationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Adaptation provider returned an invalid response",
        ) from exc
    except PlanRevisionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan changed while the adaptation was generated",
        ) from exc
