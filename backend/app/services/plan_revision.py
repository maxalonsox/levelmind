from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.mission import Mission
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.schemas.plan_revision import PlanRevisionSnapshot
from app.services.goal import get_owned_goal


def ensure_current_plan_revision(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
) -> PlanRevision:
    try:
        get_owned_goal(db, goal_id, user_id, for_update=True)
        revision = get_current_plan_revision(db, goal_id)
        if revision is None:
            revision = create_plan_revision(db, goal_id)
        db.commit()
        db.refresh(revision)
        return revision
    except Exception:
        db.rollback()
        raise


def get_current_plan_revision(
    db: Session,
    goal_id: UUID,
    *,
    for_update: bool = False,
) -> PlanRevision | None:
    statement = (
        select(PlanRevision)
        .where(PlanRevision.goal_id == goal_id)
        .order_by(PlanRevision.revision_number.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def create_plan_revision(
    db: Session,
    goal_id: UUID,
    *,
    base_revision: PlanRevision | None = None,
    adaptation_id: UUID | None = None,
) -> PlanRevision:
    if base_revision is not None and base_revision.goal_id != goal_id:
        raise ValueError("Base revision belongs to a different Goal")
    revision = PlanRevision(
        goal_id=goal_id,
        revision_number=(
            base_revision.revision_number + 1 if base_revision else 1
        ),
        snapshot=build_plan_revision_snapshot(db, goal_id).model_dump(
            mode="json"
        ),
        base_revision_id=base_revision.id if base_revision else None,
        adaptation_id=adaptation_id,
    )
    db.add(revision)
    db.flush()
    return revision


def build_plan_revision_snapshot(
    db: Session, goal_id: UUID
) -> PlanRevisionSnapshot:
    stages = list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .options(
                selectinload(Stage.missions).selectinload(Mission.tasks)
            )
            .order_by(Stage.order_index.asc())
        )
    )
    return PlanRevisionSnapshot.model_validate(
        {
            "stages": [
                {
                    "id": stage.id,
                    "title": stage.title,
                    "description": stage.description,
                    "order_index": stage.order_index,
                    "status": stage.status,
                    "missions": [
                        {
                            "id": mission.id,
                            "title": mission.title,
                            "description": mission.description,
                            "order_index": mission.order_index,
                            "estimated_difficulty": (
                                mission.estimated_difficulty
                            ),
                            "status": mission.status,
                            "tasks": [
                                {
                                    "id": task.id,
                                    "title": task.title,
                                    "description": task.description,
                                    "order_index": task.order_index,
                                    "estimated_duration_minutes": (
                                        task.estimated_duration_minutes
                                    ),
                                    "estimated_difficulty": (
                                        task.estimated_difficulty
                                    ),
                                    "xp_reward": task.xp_reward,
                                    "status": task.status,
                                }
                                for task in sorted(
                                    mission.tasks,
                                    key=lambda item: item.order_index,
                                )
                            ],
                        }
                        for mission in sorted(
                            stage.missions,
                            key=lambda item: item.order_index,
                        )
                    ],
                }
                for stage in stages
            ]
        }
    )
