from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PlanningStatus
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.generated_plan import GeneratedPlan, PersistedPlan
from app.services.goal import get_owned_goal


class GoalAlreadyHasPlanError(Exception):
    """Raised when a Goal already has a persisted planning hierarchy."""


def persist_generated_plan(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
    generated_plan: GeneratedPlan,
) -> PersistedPlan:
    try:
        get_owned_goal(db, goal_id, user_id, for_update=True)
        existing_stage_id = db.scalar(
            select(Stage.id).where(Stage.goal_id == goal_id).limit(1)
        )
        if existing_stage_id is not None:
            raise GoalAlreadyHasPlanError

        stages = _build_plan_models(goal_id, generated_plan)
        db.add_all(stages)
        db.flush()

        persisted_plan = PersistedPlan.model_validate({"stages": stages})
        db.commit()
        return persisted_plan
    except Exception:
        db.rollback()
        raise


def _build_plan_models(
    goal_id: UUID, generated_plan: GeneratedPlan
) -> list[Stage]:
    stages: list[Stage] = []

    for generated_stage in generated_plan.stages:
        stage = Stage(
            goal_id=goal_id,
            title=generated_stage.title,
            description=generated_stage.description,
            order_index=generated_stage.order_index,
            status=PlanningStatus.PENDING,
        )

        for generated_mission in generated_stage.missions:
            mission = Mission(
                title=generated_mission.title,
                description=generated_mission.description,
                order_index=generated_mission.order_index,
                estimated_difficulty=generated_mission.estimated_difficulty,
                status=PlanningStatus.PENDING,
            )

            mission.tasks = [
                Task(
                    title=generated_task.title,
                    description=generated_task.description,
                    order_index=generated_task.order_index,
                    estimated_duration_minutes=(
                        generated_task.estimated_duration_minutes
                    ),
                    xp_reward=generated_task.xp_reward,
                    status=PlanningStatus.PENDING,
                )
                for generated_task in generated_mission.tasks
            ]
            stage.missions.append(mission)

        stages.append(stage)

    return stages
