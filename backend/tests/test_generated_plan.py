from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models.enums import Difficulty, PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.generated_plan import GeneratedPlan
from app.services.generated_plan import persist_generated_plan


def valid_plan_payload() -> dict[str, Any]:
    return {
        "stages": [
            {
                "title": "Backend foundations",
                "description": "Refresh core backend concepts",
                "order_index": 0,
                "missions": [
                    {
                        "title": "Modern Python",
                        "description": "Practice current language features",
                        "order_index": 0,
                        "estimated_difficulty": "normal",
                        "tasks": [
                            {
                                "title": "Practice type hints",
                                "order_index": 0,
                                "estimated_duration_minutes": 45,
                                "xp_reward": 15,
                            },
                            {
                                "title": "Practice data modeling",
                                "order_index": 2,
                                "estimated_duration_minutes": 60,
                            },
                        ],
                    },
                    {
                        "title": "API design",
                        "order_index": 2,
                        "estimated_difficulty": "difficult",
                        "tasks": [
                            {
                                "title": "Design resource endpoints",
                                "order_index": 0,
                                "xp_reward": 20,
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Production delivery",
                "order_index": 3,
                "missions": [
                    {
                        "title": "Deployment basics",
                        "order_index": 0,
                        "tasks": [
                            {
                                "title": "Define deployment checklist",
                                "order_index": 0,
                                "estimated_duration_minutes": 30,
                                "xp_reward": 5,
                            }
                        ],
                    }
                ],
            },
        ]
    }


def persist_goal(db: Session, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="I know programming fundamentals",
        expected_outcome="Build and deploy production APIs",
    )
    db.add(goal)
    db.commit()
    return goal


def assert_invalid(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GeneratedPlan.model_validate(payload)


def test_valid_generated_plan_can_be_constructed() -> None:
    plan = GeneratedPlan.model_validate(valid_plan_payload())

    assert len(plan.stages) == 2
    assert len(plan.stages[0].missions) == 2
    assert len(plan.stages[0].missions[0].tasks) == 2
    assert plan.stages[0].missions[0].estimated_difficulty is Difficulty.NORMAL
    assert plan.stages[0].missions[0].tasks[1].xp_reward == 10


def test_generated_plan_rejects_empty_stages() -> None:
    assert_invalid({"stages": []})


def test_generated_stage_rejects_empty_missions() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"] = []
    assert_invalid(payload)


def test_generated_mission_rejects_empty_tasks() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["tasks"] = []
    assert_invalid(payload)


@pytest.mark.parametrize("level", ["stage", "mission", "task"])
def test_generated_plan_rejects_blank_titles(level: str) -> None:
    payload = valid_plan_payload()
    if level == "stage":
        payload["stages"][0]["title"] = "   "
    elif level == "mission":
        payload["stages"][0]["missions"][0]["title"] = "   "
    else:
        payload["stages"][0]["missions"][0]["tasks"][0]["title"] = "   "
    assert_invalid(payload)


def test_generated_plan_rejects_negative_order_index() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["tasks"][0]["order_index"] = -1
    assert_invalid(payload)


@pytest.mark.parametrize("duration", [0, -1])
def test_generated_task_rejects_non_positive_duration(duration: int) -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["tasks"][0][
        "estimated_duration_minutes"
    ] = duration
    assert_invalid(payload)


def test_generated_task_rejects_negative_xp_reward() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["tasks"][0]["xp_reward"] = -1
    assert_invalid(payload)


def test_generated_mission_rejects_invalid_difficulty() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["estimated_difficulty"] = "extreme"
    assert_invalid(payload)


def test_generated_plan_rejects_duplicate_stage_order_indexes() -> None:
    payload = valid_plan_payload()
    payload["stages"][1]["order_index"] = 0
    assert_invalid(payload)


def test_generated_stage_rejects_duplicate_mission_order_indexes() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][1]["order_index"] = 0
    assert_invalid(payload)


def test_generated_mission_rejects_duplicate_task_order_indexes() -> None:
    payload = valid_plan_payload()
    payload["stages"][0]["missions"][0]["tasks"][1]["order_index"] = 0
    assert_invalid(payload)


def test_persist_generated_plan_creates_complete_hierarchy(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    original_goal_title = goal.title
    generated_plan = GeneratedPlan.model_validate(valid_plan_payload())

    result = persist_generated_plan(
        db_session, goal.id, authenticated_user_id, generated_plan
    )

    stages = list(
        db_session.scalars(select(Stage).order_by(Stage.order_index.asc()))
    )
    missions = list(
        db_session.scalars(select(Mission).order_by(Mission.order_index.asc()))
    )
    tasks = list(
        db_session.scalars(select(Task).order_by(Task.order_index.asc()))
    )

    assert len(stages) == 2
    assert len(missions) == 3
    assert len(tasks) == 4
    assert len(result.stages) == 2
    assert len(result.stages[0].missions) == 2
    assert len(result.stages[0].missions[0].tasks) == 2
    assert result.stages[0].id
    assert result.stages[0].missions[0].id
    assert result.stages[0].missions[0].tasks[0].id
    assert all(stage.goal_id == goal.id for stage in stages)
    stage_ids = {stage.id for stage in stages}
    mission_ids = {mission.id for mission in missions}
    assert all(mission.stage_id in stage_ids for mission in missions)
    assert all(task.mission_id in mission_ids for task in tasks)
    assert all(stage.status == PlanningStatus.PENDING for stage in stages)
    assert all(mission.status == PlanningStatus.PENDING for mission in missions)
    assert all(task.status == PlanningStatus.PENDING for task in tasks)
    assert [stage.order_index for stage in stages] == [0, 3]
    assert sorted(task.xp_reward for task in tasks) == [5, 10, 15, 20]

    persisted_goal = db_session.get(Goal, goal.id)
    assert persisted_goal is not None
    assert persisted_goal.title == original_goal_title


def test_persist_generated_plan_rejects_goal_owned_by_another_user(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    other_users_goal = persist_goal(db_session, uuid4())
    generated_plan = GeneratedPlan.model_validate(valid_plan_payload())

    with pytest.raises(HTTPException) as exc_info:
        persist_generated_plan(
            db_session,
            other_users_goal.id,
            authenticated_user_id,
            generated_plan,
        )

    assert exc_info.value.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0


def test_persist_generated_plan_rolls_back_complete_hierarchy_on_error(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    payload = deepcopy(valid_plan_payload())
    payload["stages"][1]["missions"][0]["tasks"][0]["title"] = "Fail insert"
    generated_plan = GeneratedPlan.model_validate(payload)

    def fail_selected_task_insert(_mapper, _connection, target: Task) -> None:
        if target.title == "Fail insert":
            raise RuntimeError("Deliberate persistence failure")

    event.listen(Task, "before_insert", fail_selected_task_insert)
    try:
        with pytest.raises(RuntimeError, match="Deliberate persistence failure"):
            persist_generated_plan(
                db_session, goal.id, authenticated_user_id, generated_plan
            )
    finally:
        event.remove(Task, "before_insert", fail_selected_task_insert)

    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0
    assert db_session.scalar(select(func.count()).select_from(Mission)) == 0
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0
    assert db_session.get(Goal, goal.id) is not None
