from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.errors import AIConfigurationError
from app.ai.evaluation.contracts import EvaluationResult
from app.ai.evaluation.errors import (
    EvaluationError,
    EvaluationProviderTimeoutError,
)
from app.ai.evaluation.openai_compatible import (
    OpenAICompatibleEvaluationProvider,
)
from app.ai.openai_compatible import (
    AI_RATE_LIMIT_DETAIL,
    ai_provider_logging_context,
    is_rate_limit_error,
)
from app.auth import AuthenticatedUser, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.services.evaluation import (
    EvaluationProviderFactory,
    EvaluationService,
)
from app.services.evaluation_context import build_evaluation_context

router = APIRouter(prefix="/goals", tags=["evaluation"])


def get_evaluation_provider_factory() -> EvaluationProviderFactory:
    return lambda: OpenAICompatibleEvaluationProvider(get_settings())


@router.post(
    "/{goal_id}/evaluation/preview",
    response_model=EvaluationResult,
)
async def preview_goal_evaluation(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider_factory: Annotated[
        EvaluationProviderFactory,
        Depends(get_evaluation_provider_factory),
    ],
) -> EvaluationResult:
    context = build_evaluation_context(db, goal_id, current_user.id)
    try:
        with ai_provider_logging_context(str(goal_id)):
            return await EvaluationService(provider_factory).evaluate(context)
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
    except EvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                AI_RATE_LIMIT_DETAIL
                if is_rate_limit_error(exc)
                else "Evaluation provider returned an invalid response"
            ),
        ) from exc
