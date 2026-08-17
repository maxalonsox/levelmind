from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.schemas.mission import MissionCreate


def create_mission(
    db: Session, data: MissionCreate, stage_id: UUID, user_id: UUID
) -> Mission:
    _get_owned_stage(db, stage_id, user_id)
    mission = Mission(stage_id=stage_id, **data.model_dump())

    db.add(mission)
    db.commit()
    db.refresh(mission)

    return mission


def list_missions(db: Session, stage_id: UUID, user_id: UUID) -> list[Mission]:
    _get_owned_stage(db, stage_id, user_id)
    return list(
        db.scalars(
            select(Mission)
            .where(Mission.stage_id == stage_id)
            .order_by(Mission.order_index.asc())
        )
    )


def _get_owned_stage(db: Session, stage_id: UUID, user_id: UUID) -> Stage:
    stage = db.scalar(
        select(Stage)
        .join(Goal, Stage.goal_id == Goal.id)
        .where(Stage.id == stage_id, Goal.user_id == user_id)
    )
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found",
        )
    return stage
