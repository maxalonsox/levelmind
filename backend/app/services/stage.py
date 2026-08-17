from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.stage import Stage
from app.schemas.stage import StageCreate


def create_stage(
    db: Session, data: StageCreate, goal_id: UUID, user_id: UUID
) -> Stage:
    _get_owned_goal(db, goal_id, user_id)
    stage = Stage(goal_id=goal_id, **data.model_dump())

    db.add(stage)
    db.commit()
    db.refresh(stage)

    return stage


def list_stages(db: Session, goal_id: UUID, user_id: UUID) -> list[Stage]:
    _get_owned_goal(db, goal_id, user_id)
    return list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .order_by(Stage.order_index.asc())
        )
    )


def _get_owned_goal(db: Session, goal_id: UUID, user_id: UUID) -> Goal:
    goal = db.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )
    return goal
