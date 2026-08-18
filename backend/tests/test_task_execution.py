import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.api.plan_preview import get_planning_provider
from app.main import app
from app.models.enums import PlanningStatus
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.services import task as task_service


async def request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=payload)


def persist_goal(db: Session, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="I know Python fundamentals",
        expected_outcome="Build production APIs",
    )
    db.add(goal)
    db.commit()
    return goal


def persist_hierarchy(
    db: Session,
    user_id: UUID,
    *,
    task_count: int = 1,
) -> tuple[Goal, Stage, Mission, list[Task]]:
    goal = persist_goal(db, user_id)
    stage = Stage(goal_id=goal.id, title="Foundations", order_index=0)
    mission = Mission(title="Build an API", order_index=0)
    mission.tasks = [
        Task(
            title=f"Task {index}",
            order_index=index,
            xp_reward=10 + index * 5,
        )
        for index in range(task_count)
    ]
    stage.missions.append(mission)
    db.add(stage)
    db.commit()
    return goal, stage, mission, mission.tasks


def result_payload(
    result: str = "completed",
    difficulty: str | None = "normal",
    feedback: str | None = "The validation required extra debugging.",
) -> dict[str, Any]:
    return {
        "result": result,
        "difficulty_feedback": difficulty,
        "feedback_text": feedback,
    }


def test_complete_task_records_feedback_xp_and_completes_ancestors(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, mission, tasks = persist_hierarchy(
        db_session, authenticated_user_id
    )
    task = tasks[0]
    task.estimated_difficulty = "easy"
    db_session.commit()
    provider_dependency_calls = 0

    def fail_if_provider_is_built() -> None:
        nonlocal provider_dependency_calls
        provider_dependency_calls += 1
        raise AssertionError("Task execution must not construct an LLM provider")

    app.dependency_overrides[get_planning_provider] = fail_if_provider_is_built
    try:
        response = asyncio.run(
            request(
                "POST",
                f"/tasks/{task.id}/result",
                result_payload(),
            )
        )
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 200
    assert provider_dependency_calls == 0
    body = response.json()
    assert body["status"] == "completed"
    assert body["difficulty_feedback"] == "normal"
    assert body["feedback_text"] == result_payload()["feedback_text"]
    assert body["xp_reward"] == task.xp_reward
    assert body["xp_awarded"] == task.xp_reward
    assert datetime.fromisoformat(body["resolved_at"])

    db_session.refresh(task)
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert task.status == PlanningStatus.COMPLETED
    assert task.estimated_difficulty == "easy"
    assert task.difficulty_feedback == "normal"
    assert task.resolved_at is not None
    assert mission.status == PlanningStatus.COMPLETED
    assert stage.status == PlanningStatus.COMPLETED
    assert goal.status == "completed"

    memories = list(db_session.scalars(select(MemoryEntry)))
    assert len(memories) == 1
    memory = memories[0]
    assert memory.user_id == authenticated_user_id
    assert memory.goal_id == goal.id
    assert memory.memory_type == "observed"
    assert memory.key == "task_execution"
    assert memory.source_type == "task"
    assert memory.source_id == task.id
    assert memory.confidence == 1.0
    assert memory.value == {
        "result": "completed",
        "estimated_difficulty": "easy",
        "difficulty_feedback": "normal",
    }
    assert "feedback_text" not in memory.value


def test_skip_task_records_feedback_without_xp_and_skips_ancestors(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, mission, tasks = persist_hierarchy(
        db_session, authenticated_user_id
    )
    task = tasks[0]

    response = asyncio.run(
        request(
            "POST",
            f"/tasks/{task.id}/result",
            result_payload(
                result="skipped",
                difficulty="difficult",
                feedback="Blocked by unavailable infrastructure.",
            ),
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert response.json()["xp_awarded"] == 0
    assert response.json()["difficulty_feedback"] == "difficult"

    db_session.refresh(task)
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert task.status == PlanningStatus.SKIPPED
    assert task.feedback_text == "Blocked by unavailable infrastructure."
    assert task.resolved_at is not None
    assert mission.status == PlanningStatus.SKIPPED
    assert stage.status == PlanningStatus.SKIPPED
    assert goal.status == "active"

    memories = list(db_session.scalars(select(MemoryEntry)))
    assert len(memories) == 1
    assert memories[0].value == {
        "result": "skipped",
        "estimated_difficulty": None,
        "difficulty_feedback": "difficult",
    }
    assert "feedback_text" not in memories[0].value


def test_repeating_same_result_is_idempotent(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_hierarchy(db_session, authenticated_user_id)
    task = tasks[0]
    path = f"/tasks/{task.id}/result"

    first_response = asyncio.run(request("POST", path, result_payload()))
    db_session.refresh(task)
    first_resolved_at = task.resolved_at
    first_updated_at = task.updated_at
    second_response = asyncio.run(request("POST", path, result_payload()))

    assert first_response.status_code == 200
    assert first_response.json()["xp_awarded"] == task.xp_reward
    assert second_response.status_code == 200
    assert second_response.json()["xp_awarded"] == 0
    db_session.refresh(task)
    assert task.resolved_at == first_resolved_at
    assert task.updated_at == first_updated_at
    assert len(list(db_session.scalars(select(MemoryEntry)))) == 1

    plan_response = asyncio.run(request("GET", f"/goals/{goal.id}/plan"))
    assert plan_response.json()["progress"]["xp_earned"] == task.xp_reward


@pytest.mark.parametrize(
    ("initial_result", "new_result"),
    [("completed", "skipped"), ("skipped", "completed")],
)
def test_terminal_task_result_cannot_be_changed(
    initial_result: str,
    new_result: str,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    _, _, _, tasks = persist_hierarchy(db_session, authenticated_user_id)
    task = tasks[0]
    path = f"/tasks/{task.id}/result"
    first_response = asyncio.run(
        request("POST", path, result_payload(result=initial_result))
    )
    db_session.refresh(task)
    resolved_at = task.resolved_at
    feedback_text = task.feedback_text

    second_response = asyncio.run(
        request("POST", path, result_payload(result=new_result))
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Task already has a different terminal result"
    }
    db_session.refresh(task)
    assert task.status == initial_result
    assert task.resolved_at == resolved_at
    assert task.feedback_text == feedback_text
    assert len(list(db_session.scalars(select(MemoryEntry)))) == 1


def test_task_result_enforces_ownership(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    _, _, _, tasks = persist_hierarchy(db_session, uuid4())

    response = asyncio.run(
        request(
            "POST",
            f"/tasks/{tasks[0].id}/result",
            result_payload(),
        )
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
    db_session.refresh(tasks[0])
    assert tasks[0].status == PlanningStatus.PENDING


def test_daily_plan_endpoints_require_authentication(db_session: Session) -> None:
    goal, _, _, tasks = persist_hierarchy(db_session, uuid4())

    result_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{tasks[0].id}/result",
            result_payload(),
        )
    )
    plan_response = asyncio.run(request("GET", f"/goals/{goal.id}/plan"))

    assert result_response.status_code == 401
    assert result_response.headers["www-authenticate"] == "Bearer"
    assert plan_response.status_code == 401
    assert plan_response.headers["www-authenticate"] == "Bearer"
    db_session.refresh(tasks[0])
    assert tasks[0].status == PlanningStatus.PENDING


@pytest.mark.parametrize(
    "payload",
    [
        {
            "result": "completed",
            "difficulty_feedback": "extreme",
        },
        {
            "result": "completed",
            "feedback_text": "   ",
        },
        {
            "result": "completed",
            "feedback_text": "x" * 2001,
        },
        {
            "result": "pending",
        },
        {
            "result": "in_progress",
        },
    ],
)
def test_task_result_validates_input(
    payload: dict[str, Any],
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    _, _, _, tasks = persist_hierarchy(db_session, authenticated_user_id)

    response = asyncio.run(
        request("POST", f"/tasks/{tasks[0].id}/result", payload)
    )

    assert response.status_code == 422
    db_session.refresh(tasks[0])
    assert tasks[0].status == PlanningStatus.PENDING


def test_parent_statuses_progress_from_pending_to_in_progress_to_completed(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, mission, tasks = persist_hierarchy(
        db_session, authenticated_user_id, task_count=2
    )

    initial_plan = asyncio.run(request("GET", f"/goals/{goal.id}/plan"))
    assert initial_plan.json()["stages"][0]["status"] == "pending"
    assert initial_plan.json()["stages"][0]["missions"][0]["status"] == (
        "pending"
    )

    first_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{tasks[0].id}/result",
            result_payload(),
        )
    )
    assert first_response.status_code == 200
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert mission.status == PlanningStatus.IN_PROGRESS
    assert stage.status == PlanningStatus.IN_PROGRESS
    assert goal.status == "active"

    second_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{tasks[1].id}/result",
            result_payload(),
        )
    )
    assert second_response.status_code == 200
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert mission.status == PlanningStatus.COMPLETED
    assert stage.status == PlanningStatus.COMPLETED
    assert goal.status == "completed"


def test_get_plan_returns_ordered_hierarchy_feedback_progress_and_xp(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    later_stage = Stage(goal_id=goal.id, title="Later", order_index=2)
    earlier_stage = Stage(goal_id=goal.id, title="Earlier", order_index=0)
    later_mission = Mission(title="Later mission", order_index=2)
    earlier_mission = Mission(title="Earlier mission", order_index=0)
    pending_task = Task(title="Pending", order_index=0, xp_reward=5)
    later_mission.tasks.append(pending_task)
    completed_task = Task(title="Completed", order_index=2, xp_reward=20)
    skipped_task = Task(title="Skipped", order_index=0, xp_reward=30)
    earlier_mission.tasks.extend([completed_task, skipped_task])
    extra_mission = Mission(title="Completed mission", order_index=0)
    extra_completed_task = Task(title="Also completed", order_index=0, xp_reward=15)
    extra_mission.tasks.append(extra_completed_task)
    earlier_stage.missions.extend([later_mission, earlier_mission])
    later_stage.missions.append(extra_mission)
    db_session.add_all([later_stage, earlier_stage])
    db_session.commit()

    completed_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{completed_task.id}/result",
            result_payload(feedback="Completed with tests."),
        )
    )
    skipped_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{skipped_task.id}/result",
            result_payload(result="skipped", feedback="No longer relevant."),
        )
    )
    extra_response = asyncio.run(
        request(
            "POST",
            f"/tasks/{extra_completed_task.id}/result",
            result_payload(),
        )
    )
    assert completed_response.status_code == 200
    assert skipped_response.status_code == 200
    assert extra_response.status_code == 200

    response = asyncio.run(request("GET", f"/goals/{goal.id}/plan"))

    assert response.status_code == 200
    body = response.json()
    assert body["goal_id"] == str(goal.id)
    assert body["status"] == "active"
    assert body["progress"] == {
        "percentage": 50.0,
        "xp_earned": 35,
        "completed_tasks": 2,
        "skipped_tasks": 1,
        "pending_tasks": 1,
        "total_tasks": 4,
    }
    assert [stage["title"] for stage in body["stages"]] == [
        "Earlier",
        "Later",
    ]
    assert [
        mission["title"] for mission in body["stages"][0]["missions"]
    ] == ["Earlier mission", "Later mission"]
    returned_tasks = body["stages"][0]["missions"][0]["tasks"]
    assert [task["title"] for task in returned_tasks] == [
        "Skipped",
        "Completed",
    ]
    assert returned_tasks[0]["status"] == "skipped"
    assert returned_tasks[0]["feedback_text"] == "No longer relevant."
    assert returned_tasks[1]["status"] == "completed"
    assert returned_tasks[1]["feedback_text"] == "Completed with tests."
    assert body["stages"][0]["missions"][0]["status"] == "skipped"
    assert body["stages"][0]["status"] == "in_progress"


def test_get_plan_enforces_ownership(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, _ = persist_hierarchy(db_session, uuid4())

    response = asyncio.run(request("GET", f"/goals/{goal.id}/plan"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}


def test_task_result_rolls_back_task_and_parent_updates_on_failure(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, mission, tasks = persist_hierarchy(
        db_session, authenticated_user_id
    )
    task = tasks[0]

    def fail_stage_update(_mapper, _connection, _target: Stage) -> None:
        raise RuntimeError("Deliberate derived status failure")

    event.listen(Stage, "before_update", fail_stage_update)
    try:
        response = asyncio.run(
            request(
                "POST",
                f"/tasks/{task.id}/result",
                result_payload(),
            )
        )
    finally:
        event.remove(Stage, "before_update", fail_stage_update)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to record Task result"}
    db_session.refresh(task)
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert task.status == PlanningStatus.PENDING
    assert task.difficulty_feedback is None
    assert task.feedback_text is None
    assert task.resolved_at is None
    assert mission.status == PlanningStatus.PENDING
    assert stage.status == PlanningStatus.PENDING
    assert goal.status == "active"
    assert db_session.scalar(select(MemoryEntry)) is None


def test_task_result_rolls_back_when_memory_creation_fails(
    db_session: Session,
    authenticated_user_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    goal, stage, mission, tasks = persist_hierarchy(
        db_session, authenticated_user_id
    )
    task = tasks[0]

    def fail_memory_creation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Deliberate memory creation failure")

    monkeypatch.setattr(
        task_service,
        "add_memory_entry",
        fail_memory_creation,
    )

    response = asyncio.run(
        request(
            "POST",
            f"/tasks/{task.id}/result",
            result_payload(),
        )
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to record Task result"}
    db_session.refresh(task)
    db_session.refresh(mission)
    db_session.refresh(stage)
    db_session.refresh(goal)
    assert task.status == PlanningStatus.PENDING
    assert task.difficulty_feedback is None
    assert task.feedback_text is None
    assert task.resolved_at is None
    assert mission.status == PlanningStatus.PENDING
    assert stage.status == PlanningStatus.PENDING
    assert goal.status == "active"
    assert db_session.scalar(select(MemoryEntry)) is None
