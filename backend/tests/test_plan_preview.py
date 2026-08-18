import asyncio
from typing import Any
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.planning.contracts import PlanningGoalInput
from app.ai.planning.errors import (
    InvalidGeneratedPlanError,
    PlanningProviderTimeoutError,
)
from app.api.plan_preview import get_planning_provider
from app.main import app
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.schemas.generated_plan import GeneratedPlan


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


def preview_plan() -> GeneratedPlan:
    return GeneratedPlan.model_validate(
        {
            "stages": [
                {
                    "title": "Foundation",
                    "order_index": 0,
                    "missions": [
                        {
                            "title": "Build an API",
                            "order_index": 0,
                            "estimated_difficulty": "normal",
                            "tasks": [
                                {
                                    "title": "Implement one endpoint",
                                    "order_index": 0,
                                    "estimated_duration_minutes": 45,
                                    "xp_reward": 10,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )


class PreviewProvider:
    def __init__(self) -> None:
        self.calls: list[PlanningGoalInput] = []

    async def generate_plan(self, goal: PlanningGoalInput) -> GeneratedPlan:
        self.calls.append(goal)
        return preview_plan()


class ErrorProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def generate_plan(self, goal: PlanningGoalInput) -> GeneratedPlan:
        raise self.error


async def post_preview(goal_id: UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/goals/{goal_id}/plan/preview")


def test_plan_preview_returns_plan_without_persisting_it(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    provider = PreviewProvider()
    app.dependency_overrides[get_planning_provider] = lambda: provider

    try:
        response = asyncio.run(post_preview(goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 200
    assert response.json() == preview_plan().model_dump(mode="json")
    assert len(provider.calls) == 1
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0
    assert db_session.scalar(select(func.count()).select_from(Mission)) == 0
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0


def test_plan_preview_can_retry_for_the_same_unplanned_goal_without_duplication(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    provider = PreviewProvider()
    app.dependency_overrides[get_planning_provider] = lambda: provider

    try:
        first = asyncio.run(post_preview(goal.id))
        second = asyncio.run(post_preview(goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(provider.calls) == 2
    assert db_session.scalar(select(func.count()).select_from(Goal)) == 1
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 0


def test_plan_preview_rejects_goal_with_persisted_plan_before_provider(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    db_session.add(Stage(goal_id=goal.id, title="Existing", order_index=0))
    db_session.commit()
    provider = PreviewProvider()
    provider_dependency_calls = 0

    def provide_planning_provider() -> PreviewProvider:
        nonlocal provider_dependency_calls
        provider_dependency_calls += 1
        return provider

    app.dependency_overrides[get_planning_provider] = provide_planning_provider
    try:
        response = asyncio.run(post_preview(goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 409
    assert response.json() == {"detail": "Goal already has a persisted plan"}
    assert provider_dependency_calls == 0
    assert provider.calls == []
    assert db_session.scalar(select(func.count()).select_from(Stage)) == 1


def test_plan_preview_enforces_goal_ownership(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    other_users_goal = persist_goal(db_session, uuid4())
    provider = PreviewProvider()
    provider_dependency_calls = 0

    def provide_planning_provider() -> PreviewProvider:
        nonlocal provider_dependency_calls
        provider_dependency_calls += 1
        return provider

    app.dependency_overrides[get_planning_provider] = provide_planning_provider

    try:
        response = asyncio.run(post_preview(other_users_goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 404
    assert provider_dependency_calls == 0
    assert provider.calls == []


def test_plan_preview_maps_provider_timeout_to_504(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    provider = ErrorProvider(
        PlanningProviderTimeoutError("Internal timeout details")
    )
    app.dependency_overrides[get_planning_provider] = lambda: provider

    try:
        response = asyncio.run(post_preview(goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 504
    assert response.json() == {"detail": "Planning provider timed out"}


def test_plan_preview_hides_invalid_provider_response_details(
    db_session: Session, authenticated_user_id: UUID
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    provider = ErrorProvider(
        InvalidGeneratedPlanError("Sensitive provider response")
    )
    app.dependency_overrides[get_planning_provider] = lambda: provider

    try:
        response = asyncio.run(post_preview(goal.id))
    finally:
        app.dependency_overrides.pop(get_planning_provider, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Planning provider returned an invalid response"
    }
