import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.errors import AIConfigurationError
from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationResult,
)
from app.ai.evaluation.errors import (
    EvaluationProviderAPIError,
    EvaluationProviderTimeoutError,
    InvalidEvaluationJSONError,
    InvalidEvaluationResultError,
)
from app.api.evaluation_preview import get_evaluation_provider_factory
from app.main import app
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task


async def post_evaluation(goal_id: UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/goals/{goal_id}/evaluation/preview")


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


def persist_plan(
    db: Session,
    goal: Goal,
    *,
    resolved_tasks: int,
    pending_tasks: int,
) -> list[Task]:
    stage = Stage(goal_id=goal.id, title="Backend", order_index=0)
    mission = Mission(title="API delivery", order_index=0)
    tasks = [
        Task(
            title=f"Resolved {index}",
            order_index=index,
            status="completed",
            difficulty_feedback="normal",
            feedback_text="Implementation completed with tests.",
            xp_reward=10,
        )
        for index in range(resolved_tasks)
    ]
    tasks.extend(
        Task(
            title=f"Pending {index}",
            order_index=resolved_tasks + index,
            xp_reward=10,
        )
        for index in range(pending_tasks)
    )
    mission.tasks = tasks
    stage.missions.append(mission)
    db.add(stage)
    db.commit()
    return tasks


def valid_result() -> EvaluationResult:
    return EvaluationResult(
        status="on_track",
        summary="The observed execution is consistent so far.",
        signals=[
            {
                "type": "consistent_progress",
                "description": "Three resolved Tasks were completed.",
                "severity": "low",
            }
        ],
        needs_adaptation=False,
    )


class FakeProvider:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.contexts: list[EvaluationContext] = []
        self.closed = False

    async def evaluate(self, context: EvaluationContext) -> Any:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.result

    async def close(self) -> None:
        self.closed = True


def test_evaluation_preview_returns_insufficient_data_without_provider(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal, resolved_tasks=1, pending_tasks=9)
    factory_calls = 0

    def fail_if_constructed() -> FakeProvider:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("Provider must not be built for insufficient data")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: fail_if_constructed
    )
    try:
        response = asyncio.run(post_evaluation(goal.id))
    finally:
        app.dependency_overrides.pop(
            get_evaluation_provider_factory, None
        )

    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_data"
    assert response.json()["needs_adaptation"] is False
    assert factory_calls == 0


def test_evaluation_preview_passes_minimized_context_without_persisting(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    tasks = persist_plan(db_session, goal, resolved_tasks=3, pending_tasks=2)
    db_session.add(
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="task_execution",
            value={
                "result": "completed",
                "estimated_difficulty": "normal",
                "difficulty_feedback": "difficult",
                "feedback_text": "Do not duplicate this text.",
            },
            source_type="task",
            source_id=tasks[0].id,
            confidence=1,
        )
    )
    db_session.commit()
    provider = FakeProvider(result=valid_result())
    before_counts = (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
    )

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: provider
    )
    try:
        response = asyncio.run(post_evaluation(goal.id))
    finally:
        app.dependency_overrides.pop(
            get_evaluation_provider_factory, None
        )

    assert response.status_code == 200
    assert response.json() == valid_result().model_dump(mode="json")
    assert provider.closed is True
    assert len(provider.contexts) == 1
    context = provider.contexts[0]
    assert context.metrics.total_tasks == 5
    assert context.metrics.completed_tasks == 3
    assert context.metrics.xp_earned == 30
    assert [
        observation.model_dump(mode="json")
        for observation in context.recent_observed_task_execution_history
    ] == [
        {
            "result": "completed",
            "estimated_difficulty": "normal",
            "difficulty_feedback": "difficult",
        }
    ]
    context_text = str(context.model_dump(mode="json"))
    assert str(goal.id) not in context_text
    assert str(goal.user_id) not in context_text
    assert "Do not duplicate this text." not in context_text
    assert (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
    ) == before_counts
    assert all(task.status == "completed" for task in tasks[:3])
    assert all(task.status == "pending" for task in tasks[3:])


def test_evaluation_preview_requires_authentication(db_session: Session) -> None:
    goal = persist_goal(db_session, uuid4())

    response = asyncio.run(post_evaluation(goal.id))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_evaluation_preview_enforces_ownership_before_provider(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, uuid4())
    persist_plan(db_session, goal, resolved_tasks=3, pending_tasks=0)
    factory_calls = 0

    def provider_factory() -> FakeProvider:
        nonlocal factory_calls
        factory_calls += 1
        return FakeProvider(result=valid_result())

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: provider_factory
    )
    try:
        response = asyncio.run(post_evaluation(goal.id))
    finally:
        app.dependency_overrides.pop(
            get_evaluation_provider_factory, None
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}
    assert factory_calls == 0


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            EvaluationProviderTimeoutError("internal timeout"),
            504,
            "Evaluation provider timed out",
        ),
        (
            EvaluationProviderAPIError("provider body"),
            502,
            "Evaluation provider returned an invalid response",
        ),
        (
            InvalidEvaluationResultError("invalid content"),
            502,
            "Evaluation provider returned an invalid response",
        ),
        (
            InvalidEvaluationJSONError("invalid JSON"),
            502,
            "Evaluation provider returned an invalid response",
        ),
    ],
)
def test_evaluation_preview_maps_provider_errors(
    error: Exception,
    expected_status: int,
    expected_detail: str,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal, resolved_tasks=3, pending_tasks=0)
    provider = FakeProvider(error=error)
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: provider
    )
    try:
        response = asyncio.run(post_evaluation(goal.id))
    finally:
        app.dependency_overrides.pop(
            get_evaluation_provider_factory, None
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert provider.closed is True


def test_evaluation_preview_maps_incomplete_configuration_to_503(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal, resolved_tasks=3, pending_tasks=0)

    def invalid_configuration() -> FakeProvider:
        raise AIConfigurationError("Missing AI configuration: AI_API_KEY")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: invalid_configuration
    )
    try:
        response = asyncio.run(post_evaluation(goal.id))
    finally:
        app.dependency_overrides.pop(
            get_evaluation_provider_factory, None
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Missing AI configuration: AI_API_KEY"
    }
