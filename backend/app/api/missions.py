from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.schemas.mission import MissionCreate, MissionResponse
from app.services.mission import create_mission, list_missions

router = APIRouter(prefix="/stages/{stage_id}/missions", tags=["missions"])


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission_endpoint(
    stage_id: UUID,
    data: MissionCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MissionResponse:
    mission = create_mission(db, data, stage_id, current_user.id)
    return MissionResponse.model_validate(mission)


@router.get("", response_model=list[MissionResponse])
def list_missions_endpoint(
    stage_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MissionResponse]:
    return [
        MissionResponse.model_validate(mission)
        for mission in list_missions(db, stage_id, current_user.id)
    ]
