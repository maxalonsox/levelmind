from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.stage import StageCreate, StageResponse
from app.services.stage import create_stage, list_stages

router = APIRouter(prefix="/goals/{goal_id}/stages", tags=["stages"])


@router.post("", response_model=StageResponse, status_code=status.HTTP_201_CREATED)
def create_stage_endpoint(
    goal_id: UUID,
    data: StageCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StageResponse:
    stage = create_stage(db, data, goal_id, current_user.id)
    return StageResponse.model_validate(stage)


@router.get("", response_model=list[StageResponse])
def list_stages_endpoint(
    goal_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StageResponse]:
    return [
        StageResponse.model_validate(stage)
        for stage in list_stages(db, goal_id, current_user.id)
    ]
