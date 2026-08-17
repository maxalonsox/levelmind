from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.task import TaskCreate


def create_task(
    db: Session, data: TaskCreate, mission_id: UUID, user_id: UUID
) -> Task:
    _get_owned_mission(db, mission_id, user_id)
    task = Task(mission_id=mission_id, **data.model_dump())

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def list_tasks(db: Session, mission_id: UUID, user_id: UUID) -> list[Task]:
    _get_owned_mission(db, mission_id, user_id)
    return list(
        db.scalars(
            select(Task)
            .where(Task.mission_id == mission_id)
            .order_by(Task.order_index.asc())
        )
    )


def _get_owned_mission(db: Session, mission_id: UUID, user_id: UUID) -> Mission:
    mission = db.scalar(
        select(Mission)
        .join(Stage, Mission.stage_id == Stage.id)
        .join(Goal, Stage.goal_id == Goal.id)
        .where(Mission.id == mission_id, Goal.user_id == user_id)
    )
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        )
    return mission
