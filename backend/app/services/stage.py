from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stage import Stage
from app.schemas.stage import StageCreate
from app.services.goal import get_owned_goal


def create_stage(
    db: Session, data: StageCreate, goal_id: UUID, user_id: UUID
) -> Stage:
    get_owned_goal(db, goal_id, user_id)
    stage = Stage(goal_id=goal_id, **data.model_dump())

    db.add(stage)
    db.commit()
    db.refresh(stage)

    return stage


def list_stages(db: Session, goal_id: UUID, user_id: UUID) -> list[Stage]:
    get_owned_goal(db, goal_id, user_id)
    return list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .order_by(Stage.order_index.asc())
        )
    )
