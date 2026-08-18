from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.planning.contracts import PlanningLLMProvider
from app.ai.planning.errors import (
    AIConfigurationError,
    PlanningError,
    PlanningProviderTimeoutError,
)
from app.ai.planning.openai_compatible import OpenAICompatiblePlanningProvider
from app.auth import AuthenticatedUser, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.goal import Goal
from app.models.stage import Stage
from app.schemas.generated_plan import GeneratedPlan
from app.services.goal import get_owned_goal
from app.services.planning import PlanningService

router = APIRouter(prefix="/goals", tags=["planning"])


async def get_planning_provider() -> AsyncIterator[PlanningLLMProvider]:
    try:
        provider = OpenAICompatiblePlanningProvider(get_settings())
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        yield provider
    finally:
        await provider.close()


def get_preview_goal(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Goal:
    goal = get_owned_goal(db, goal_id, current_user.id)
    if db.scalar(select(Stage.id).where(Stage.goal_id == goal.id).limit(1)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Goal already has a persisted plan",
        )
    return goal


@router.post("/{goal_id}/plan/preview", response_model=GeneratedPlan)
async def preview_goal_plan(
    goal: Annotated[Goal, Depends(get_preview_goal)],
    provider: Annotated[
        PlanningLLMProvider, Depends(get_planning_provider)
    ],
) -> GeneratedPlan:
    try:
        return await PlanningService(provider).generate_plan(goal)
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PlanningProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Planning provider timed out",
        ) from exc
    except PlanningError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Planning provider returned an invalid response",
        ) from exc
