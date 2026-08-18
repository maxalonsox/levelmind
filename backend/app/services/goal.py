from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.schemas.goal import GoalCreate


class ActiveGoalAlreadyExistsError(Exception):
    """Raised when a user tries to create a second active Goal."""


def create_goal(db: Session, data: GoalCreate, user_id: UUID) -> Goal:
    if _has_active_goal(db, user_id):
        raise ActiveGoalAlreadyExistsError

    goal = Goal(
        user_id=user_id,
        title=data.title,
        current_situation=data.current_situation,
        expected_outcome=data.expected_outcome,
        target_timeframe=data.target_timeframe,
        availability=data.availability,
    )

    try:
        db.add(goal)
        db.commit()
        db.refresh(goal)
    except IntegrityError:
        db.rollback()
        if _has_active_goal(db, user_id):
            raise ActiveGoalAlreadyExistsError from None
        raise

    return goal


def _has_active_goal(db: Session, user_id: UUID) -> bool:
    return (
        db.scalar(
            select(Goal.id)
            .where(Goal.user_id == user_id, Goal.status == "active")
            .limit(1)
        )
        is not None
    )


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


def get_active_goal(db: Session, user_id: UUID) -> Goal:
    goal = db.scalar(
        select(Goal)
        .where(Goal.user_id == user_id, Goal.status == "active")
        .order_by(Goal.created_at.desc(), Goal.id.desc())
        .limit(1)
    )
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active goal not found",
        )
    return goal


def delete_owned_goal(db: Session, goal_id: UUID, user_id: UUID) -> None:
    try:
        goal = get_owned_goal(db, goal_id, user_id, for_update=True)
        db.execute(
            delete(MemoryEntry).where(
                MemoryEntry.goal_id == goal.id,
            )
        )
        db.delete(goal)
        db.commit()
    except Exception:
        db.rollback()
        raise
