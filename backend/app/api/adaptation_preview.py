from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import AdaptationDecision
from app.ai.adaptation.errors import (
    AdaptationError,
    AdaptationProviderTimeoutError,
)
from app.ai.adaptation.openai_compatible import (
    OpenAICompatibleAdaptationProvider,
)
from app.ai.errors import AIConfigurationError
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
    evaluation_context = build_evaluation_context(
        db, goal_id, current_user.id
    )
    try:
        evaluation = await EvaluationService(
            evaluation_provider_factory
        ).evaluate(evaluation_context)
        adaptation_service = AdaptationService(adaptation_provider_factory)
        if not evaluation.needs_adaptation:
            proposal = await adaptation_service.propose(evaluation)
            return AdaptationPreviewResponse(
                **proposal.model_dump(),
                needs_adaptation=evaluation.needs_adaptation,
                adaptation=None,
            )

        base_revision = ensure_current_plan_revision(
            db, goal_id, current_user.id
        )
        adaptation_context = build_adaptation_context(
            db,
            goal_id,
            current_user.id,
            evaluation_context,
            evaluation,
        )
        proposal = await adaptation_service.propose(
            evaluation, adaptation_context
        )
        adaptation = None
        if proposal.decision is AdaptationDecision.PROPOSE_CHANGES:
            adaptation = persist_plan_adaptation(
                db,
                goal_id,
                current_user.id,
                proposal,
                base_revision.id,
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
