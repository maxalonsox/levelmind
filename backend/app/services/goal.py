from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.schemas.goal import GoalCreate


def create_goal(db: Session, data: GoalCreate, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title=data.title,
        current_situation=data.current_situation,
        expected_outcome=data.expected_outcome,
        target_timeframe=data.target_timeframe,
        availability=data.availability,
    )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    return goal


def get_owned_goal(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
    *,
    for_update: bool = False,
) -> Goal:
    statement = select(Goal).where(
        Goal.id == goal_id, Goal.user_id == user_id
    )
    if for_update:
        statement = statement.with_for_update()

    goal = db.scalar(statement)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )
    return goal
