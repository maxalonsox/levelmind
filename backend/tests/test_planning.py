import asyncio
from typing import Any
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task


async def request(
    method: str, path: str, payload: dict[str, Any] | None = None
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


def persist_stage(db: Session, goal: Goal, order_index: int = 0) -> Stage:
    stage = Stage(goal_id=goal.id, title="Foundations", order_index=order_index)
    db.add(stage)
    db.commit()
    return stage


def persist_mission(db: Session, stage: Stage, order_index: int = 0) -> Mission:
    mission = Mission(
        stage_id=stage.id, title="Build an API", order_index=order_index
    )
    db.add(mission)
    db.commit()
    return mission


def test_create_stage_for_existing_goal(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)

    response = asyncio.run(
        request(
            "POST",
            f"/goals/{goal.id}/stages",
            {
                "title": "Learn FastAPI",
                "description": "Cover the fundamentals",
                "order_index": 0,
            },
        )
    )

    assert response.status_code == 201
    assert response.json()["goal_id"] == str(goal.id)
    assert response.json()["status"] == "pending"
    assert db_session.scalar(select(Stage)) is not None


def test_create_stage_for_missing_goal_returns_404(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    response = asyncio.run(
        request(
            "POST",
            f"/goals/{uuid4()}/stages",
            {"title": "Learn FastAPI", "order_index": 0},
        )
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}
    assert db_session.scalar(select(Stage)) is None


def test_create_mission_for_existing_stage(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    stage = persist_stage(db_session, goal)

    response = asyncio.run(
        request(
            "POST",
            f"/stages/{stage.id}/missions",
            {
                "title": "Create first endpoint",
                "order_index": 0,
                "estimated_difficulty": "normal",
            },
        )
    )

    assert response.status_code == 201
    assert response.json()["stage_id"] == str(stage.id)
    assert response.json()["estimated_difficulty"] == "normal"
    assert db_session.scalar(select(Mission)) is not None


def test_create_task_for_existing_mission(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    stage = persist_stage(db_session, goal)
    mission = persist_mission(db_session, stage)

    response = asyncio.run(
        request(
            "POST",
            f"/missions/{mission.id}/tasks",
            {
                "title": "Define the response schema",
                "order_index": 0,
                "estimated_duration_minutes": 30,
            },
        )
    )

    assert response.status_code == 201
    assert response.json()["mission_id"] == str(mission.id)
    assert response.json()["xp_reward"] == 10
    assert db_session.scalar(select(Task)) is not None


def test_create_rejects_invalid_status(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)

    response = asyncio.run(
        request(
            "POST",
            f"/goals/{goal.id}/stages",
            {"title": "Invalid stage", "order_index": 0, "status": "blocked"},
        )
    )

    assert response.status_code == 422
    assert db_session.scalar(select(Stage)) is None


def test_create_task_rejects_invalid_values(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    stage = persist_stage(db_session, goal)
    mission = persist_mission(db_session, stage)

    response = asyncio.run(
        request(
            "POST",
            f"/missions/{mission.id}/tasks",
            {
                "title": "Invalid task",
                "order_index": -1,
                "estimated_duration_minutes": 0,
                "difficulty_feedback": "impossible",
                "xp_reward": -1,
            },
        )
    )

    assert response.status_code == 422
    assert db_session.scalar(select(Task)) is None


def test_list_endpoints_order_by_order_index(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    later_stage = persist_stage(db_session, goal, order_index=2)
    earlier_stage = persist_stage(db_session, goal, order_index=1)
    later_mission = persist_mission(db_session, earlier_stage, order_index=2)
    earlier_mission = persist_mission(db_session, earlier_stage, order_index=1)
    db_session.add_all(
        [
            Task(mission_id=earlier_mission.id, title="Later", order_index=2),
            Task(mission_id=earlier_mission.id, title="Earlier", order_index=1),
        ]
    )
    db_session.commit()

    stages_response = asyncio.run(request("GET", f"/goals/{goal.id}/stages"))
    missions_response = asyncio.run(
        request("GET", f"/stages/{earlier_stage.id}/missions")
    )
    tasks_response = asyncio.run(
        request("GET", f"/missions/{earlier_mission.id}/tasks")
    )

    assert stages_response.status_code == 200
    assert [item["id"] for item in stages_response.json()] == [
        str(earlier_stage.id),
        str(later_stage.id),
    ]
    assert missions_response.status_code == 200
    assert [item["id"] for item in missions_response.json()] == [
        str(earlier_mission.id),
        str(later_mission.id),
    ]
    assert tasks_response.status_code == 200
    assert [item["title"] for item in tasks_response.json()] == [
        "Earlier",
        "Later",
    ]


def test_nested_resources_are_hidden_from_other_users(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    other_goal = persist_goal(db_session, uuid4())
    other_stage = persist_stage(db_session, other_goal)
    other_mission = persist_mission(db_session, other_stage)

    stages_response = asyncio.run(
        request("GET", f"/goals/{other_goal.id}/stages")
    )
    missions_response = asyncio.run(
        request("GET", f"/stages/{other_stage.id}/missions")
    )
    tasks_response = asyncio.run(
        request("GET", f"/missions/{other_mission.id}/tasks")
    )

    assert stages_response.status_code == 404
    assert missions_response.status_code == 404
    assert tasks_response.status_code == 404
