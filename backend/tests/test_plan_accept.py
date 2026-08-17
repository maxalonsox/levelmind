import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.api.plan_accept as plan_accept_api
from app.api.plan_preview import get_planning_provider
from app.main import app
from app.models.enums import PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task


def persist_goal(db: Session, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="I know Python fundamentals",
        expected_outcome="Build production APIs",
        target_timeframe="Six months",
        availability="Eight hours per week",
    )
    db.add(goal)
    db.commit()
    return goal


def accepted_plan_payload() -> dict[str, Any]:
    return {
        "stages": [
            {
                "title": "API foundations",
                "description": "Build reliable HTTP APIs",
                "order_index": 0,
                "missions": [
                    {
                        "title": "Validated endpoints",
                        "description": "Implement one complete resource",
                        "order_index": 0,
                        "estimated_difficulty": "normal",
                        "tasks": [
                            {
                                "title": "Implement create endpoint",
                                "description": "Validate its request body",
                                "order_index": 0,
                                "estimated_duration_minutes": 60,
                                "xp_reward": 15,
                            },
                            {
                                "title": "Test invalid requests",
                                "description": None,
                                "order_index": 1,
                                "estimated_duration_minutes": 45,
                                "xp_reward": 10,
                            },
                        ],
                    }
                ],
            },
            {
                "title": "Production readiness",
                "description": None,
                "order_index": 2,
                "missions": [
                    {
                        "title": "Service observability",
                        "description": None,
                        "order_index": 1,
                        "estimated_difficulty": "difficult",
                        "tasks": [
                            {
                                "title": "Add structured request logs",
                                "description": "Include a correlation ID",
                                "order_index": 3,
                                "estimated_duration_minutes": 90,
                                "xp_reward": 20,
                            }
                        ],
                    }
                ],
            },
        ]
    }


async def post_accept(goal_id: UUID, payload: dict[str, Any]) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/goals/{goal_id}/plan/accept", json=payload
        )


def test_plan_accept_persists_exact_approved_hierarchy_without_llm(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    payload = accepted_plan_payload()
    provider_dependency_calls = 0

    def fail_if_provider_is_built() -> None:
        nonlocal provider_dependency_calls
        provider_dependency_calls += 1
        raise AssertionError("Accept must not construct an LLM provider")

    app.dependency_overrides[get_planning_provider] = fail_if_provider_is_built
    try:
        response = asyncio.run(post_accept(goal.id, payload))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 201
    assert provider_dependency_calls == 0

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
    assert len(missions) == 2
    assert len(tasks) == 3
    assert all(stage.goal_id == goal.id for stage in stages)
    stage_ids = {stage.id for stage in stages}
    mission_ids = {mission.id for mission in missions}
    assert all(mission.stage_id in stage_ids for mission in missions)
    assert all(task.mission_id in mission_ids for task in tasks)
    assert all(stage.status == PlanningStatus.PENDING for stage in stages)
    assert all(mission.status == PlanningStatus.PENDING for mission in missions)
    assert all(task.status == PlanningStatus.PENDING for task in tasks)

    body = response.json()
    assert len(body["stages"]) == len(payload["stages"])
    assert UUID(body["stages"][0]["id"])
    assert UUID(body["stages"][0]["missions"][0]["id"])
    assert UUID(body["stages"][0]["missions"][0]["tasks"][0]["id"])
    assert body["stages"][0]["created_at"]
    assert body["stages"][0]["updated_at"]

    for expected_stage, actual_stage in zip(payload["stages"], body["stages"]):
        assert actual_stage["title"] == expected_stage["title"]
        assert actual_stage["description"] == expected_stage["description"]
        assert actual_stage["order_index"] == expected_stage["order_index"]
        for expected_mission, actual_mission in zip(
            expected_stage["missions"], actual_stage["missions"]
        ):
            assert actual_mission["title"] == expected_mission["title"]
            assert actual_mission["description"] == expected_mission["description"]
            assert (
                actual_mission["estimated_difficulty"]
                == expected_mission["estimated_difficulty"]
            )
            assert actual_mission["order_index"] == expected_mission["order_index"]
            for expected_task, actual_task in zip(
                expected_mission["tasks"], actual_mission["tasks"]
            ):
                assert actual_task["title"] == expected_task["title"]
                assert actual_task["description"] == expected_task["description"]
                assert actual_task["order_index"] == expected_task["order_index"]
                assert (
                    actual_task["estimated_duration_minutes"]
                    == expected_task["estimated_duration_minutes"]
                )
                assert actual_task["xp_reward"] == expected_task["xp_reward"]
                assert actual_task["status"] == "pending"


def test_plan_accept_requires_authentication(db_session: Session) -> None:
    goal = persist_goal(db_session, uuid4())

    response = asyncio.run(post_accept(goal.id, accepted_plan_payload()))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0


def test_plan_accept_hides_goals_owned_by_another_user(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    other_users_goal = persist_goal(db_session, uuid4())

    response = asyncio.run(
        post_accept(other_users_goal.id, accepted_plan_payload())
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0


def test_plan_accept_rejects_invalid_generated_plan(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)

    response = asyncio.run(post_accept(goal.id, {"stages": []}))

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0


def test_plan_accept_rejects_second_plan_without_creating_records(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    first_payload = accepted_plan_payload()
    second_payload = accepted_plan_payload()
    second_payload["stages"][0]["title"] = "Replacement must not persist"

    first_response = asyncio.run(post_accept(goal.id, first_payload))
    counts_after_first = (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
    )
    second_response = asyncio.run(post_accept(goal.id, second_payload))

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Goal already has a persisted plan"
    }
    assert (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
    ) == counts_after_first
    assert db_session.scalar(select(Stage.title).order_by(Stage.order_index)) == (
        first_payload["stages"][0]["title"]
    )


def test_plan_accept_hides_unexpected_persistence_details(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)

    def fail_persistence(*_args: object) -> None:
        raise RuntimeError("sensitive database details")

    monkeypatch.setattr(
        plan_accept_api, "persist_generated_plan", fail_persistence
    )

    response = asyncio.run(post_accept(goal.id, accepted_plan_payload()))

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to persist accepted plan"}
