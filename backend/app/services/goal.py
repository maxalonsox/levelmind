from uuid import UUID

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
