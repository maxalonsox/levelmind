import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.adaptation_preview import get_adaptation_provider_factory
from app.main import app
from app.models.enums import AdaptationStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task
from app.services.plan_revision import ensure_current_plan_revision


async def post_reject(goal_id: UUID, adaptation_id: UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/goals/{goal_id}/adaptations/{adaptation_id}/reject"
        )


def persist_plan(
    db: Session, user_id: UUID
) -> tuple[Goal, Stage, Mission, Task]:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="Python fundamentals",
        expected_outcome="Build production APIs",
    )
    stage = Stage(goal=goal, title="Backend", order_index=0)
    mission = Mission(stage=stage, title="API delivery", order_index=0)
    task = Task(
        mission=mission,
        title="Implement endpoint",
        order_index=0,
        estimated_duration_minutes=45,
        estimated_difficulty="normal",
        xp_reward=15,
    )
    db.add(goal)
    db.commit()
    return goal, stage, mission, task


def proposal() -> dict[str, Any]:
    return {
        "decision": "propose_changes",
        "summary": "Increase one duration estimate.",
        "rationale": "Execution evidence supports one bounded adjustment.",
        "changes": [
            {
                "type": "adjust_task_duration",
                "target": {
                    "stage_order_index": 0,
                    "stage_title": "Backend",
                    "mission_order_index": 0,
                    "mission_title": "API delivery",
                    "task_order_index": 0,
                    "task_title": "Implement endpoint",
                },
                "reason": "The estimate is too short.",
                "estimated_duration_minutes": 90,
            }
        ],
    }


def persist_adaptation(
    db: Session,
    goal: Goal,
    *,
    status: AdaptationStatus = AdaptationStatus.PENDING,
) -> PlanAdaptation:
    revision = ensure_current_plan_revision(db, goal.id, goal.user_id)
    adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=revision.id,
        proposal=proposal(),
        status=status,
    )
    db.add(adaptation)
    db.commit()
    return adaptation


def test_reject_pending_adaptation_records_only_the_human_decision(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, mission, task = persist_plan(
        db_session, authenticated_user_id
    )
    adaptation = persist_adaptation(db_session, goal)
    original_proposal = adaptation.proposal
    original_base_revision_id = adaptation.base_revision_id
    original_plan = (
        stage.title,
        stage.order_index,
        stage.status,
        mission.title,
        mission.order_index,
        mission.status,
        task.title,
        task.order_index,
        task.status,
        task.estimated_duration_minutes,
        task.estimated_difficulty,
    )
    revision_count = db_session.scalar(
        select(func.count()).select_from(PlanRevision)
    )
    provider_calls = 0

    def fail_if_provider_is_built() -> None:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("Reject must not construct an LLM provider")

    app.dependency_overrides[get_adaptation_provider_factory] = (
        fail_if_provider_is_built
    )
    try:
        response = asyncio.run(post_reject(goal.id, adaptation.id))
    finally:
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    assert set(response.json()) == {
        "adaptation_id",
        "status",
        "reviewed_at",
    }
    assert response.json()["adaptation_id"] == str(adaptation.id)
    assert response.json()["status"] == "rejected"
    assert response.json()["reviewed_at"] is not None
    assert provider_calls == 0

    db_session.refresh(adaptation)
    db_session.refresh(stage)
    db_session.refresh(mission)
    db_session.refresh(task)
    assert adaptation.status == AdaptationStatus.REJECTED
    assert adaptation.reviewed_at is not None
    assert adaptation.proposal == original_proposal
    assert adaptation.base_revision_id == original_base_revision_id
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision))
        == revision_count
    )
    assert (
        stage.title,
        stage.order_index,
        stage.status,
        mission.title,
        mission.order_index,
        mission.status,
        task.title,
        task.order_index,
        task.status,
        task.estimated_duration_minutes,
        task.estimated_difficulty,
    ) == original_plan


def test_reject_requires_authentication(db_session: Session) -> None:
    goal, _, _, _ = persist_plan(db_session, uuid4())
    adaptation = persist_adaptation(db_session, goal)

    response = asyncio.run(post_reject(goal.id, adaptation.id))

    assert response.status_code == 401


def test_reject_hides_foreign_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    foreign_goal, _, _, _ = persist_plan(db_session, uuid4())
    adaptation = persist_adaptation(db_session, foreign_goal)

    response = asyncio.run(post_reject(foreign_goal.id, adaptation.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}


def test_reject_hides_adaptation_from_another_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    owned_goal, _, _, _ = persist_plan(db_session, authenticated_user_id)
    other_goal, _, _, _ = persist_plan(db_session, authenticated_user_id)
    adaptation = persist_adaptation(db_session, other_goal)

    response = asyncio.run(post_reject(owned_goal.id, adaptation.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Adaptation not found"}


def test_reject_returns_not_found_for_missing_adaptation(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, _ = persist_plan(db_session, authenticated_user_id)

    response = asyncio.run(post_reject(goal.id, uuid4()))

    assert response.status_code == 404
    assert response.json() == {"detail": "Adaptation not found"}


@pytest.mark.parametrize(
    "reviewed_status",
    [AdaptationStatus.ACCEPTED, AdaptationStatus.REJECTED],
)
def test_reject_requires_pending_adaptation(
    reviewed_status: AdaptationStatus,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, _ = persist_plan(db_session, authenticated_user_id)
    adaptation = persist_adaptation(
        db_session, goal, status=reviewed_status
    )

    response = asyncio.run(post_reject(goal.id, adaptation.id))

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Adaptation has already been reviewed"
    }


def test_second_reject_returns_conflict(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, _ = persist_plan(db_session, authenticated_user_id)
    adaptation = persist_adaptation(db_session, goal)

    first = asyncio.run(post_reject(goal.id, adaptation.id))
    second = asyncio.run(post_reject(goal.id, adaptation.id))

    assert first.status_code == 200
    assert second.status_code == 409


def test_reject_rolls_back_when_persistence_fails(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, _ = persist_plan(db_session, authenticated_user_id)
    adaptation = persist_adaptation(db_session, goal)

    def fail_update(_mapper, _connection, target: PlanAdaptation) -> None:
        if target.id == adaptation.id:
            raise RuntimeError("Deliberate PlanAdaptation update failure")

    event.listen(PlanAdaptation, "before_update", fail_update)
    try:
        response = asyncio.run(post_reject(goal.id, adaptation.id))
    finally:
        event.remove(PlanAdaptation, "before_update", fail_update)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to reject adaptation"}
    db_session.refresh(adaptation)
    assert adaptation.status == AdaptationStatus.PENDING
    assert adaptation.reviewed_at is None
