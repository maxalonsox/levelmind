import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.services.adaptation_acceptance as acceptance_service
from app.api.adaptation_preview import get_adaptation_provider_factory
from app.main import app
from app.models.enums import AdaptationStatus, PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task
from app.services.plan_revision import (
    create_plan_revision,
    ensure_current_plan_revision,
)


async def post_accept(goal_id: UUID, adaptation_id: UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/goals/{goal_id}/adaptations/{adaptation_id}/accept"
        )


def persist_plan(
    db: Session, user_id: UUID
) -> tuple[Goal, Stage, Mission, list[Task]]:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="Python fundamentals",
        expected_outcome="Build production APIs",
    )
    stage = Stage(goal=goal, title="Backend", order_index=0)
    mission = Mission(stage=stage, title="API delivery", order_index=0)
    mission.tasks = [
        Task(
            title="Design endpoint",
            order_index=0,
            estimated_duration_minutes=30,
            estimated_difficulty="easy",
            xp_reward=10,
        ),
        Task(
            title="Implement endpoint",
            order_index=1,
            estimated_duration_minutes=45,
            estimated_difficulty="normal",
            xp_reward=15,
        ),
        Task(
            title="Test endpoint",
            order_index=2,
            estimated_duration_minutes=30,
            estimated_difficulty="normal",
            xp_reward=10,
        ),
    ]
    db.add(goal)
    db.commit()
    return goal, stage, mission, mission.tasks


def target(task: Task) -> dict[str, Any]:
    return {
        "stage_order_index": 0,
        "stage_title": "Backend",
        "mission_order_index": 0,
        "mission_title": "API delivery",
        "task_order_index": task.order_index,
        "task_title": task.title,
    }


def proposal(changes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decision": "propose_changes",
        "summary": "Apply reviewed plan changes.",
        "rationale": "Execution evidence supports these bounded changes.",
        "changes": changes,
    }


def persist_adaptation(
    db: Session,
    goal: Goal,
    proposal_payload: dict[str, Any],
    *,
    status: AdaptationStatus = AdaptationStatus.PENDING,
) -> tuple[PlanAdaptation, PlanRevision]:
    revision = ensure_current_plan_revision(db, goal.id, goal.user_id)
    adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=revision.id,
        proposal=proposal_payload,
        status=status,
    )
    db.add(adaptation)
    db.commit()
    return adaptation, revision


def test_accept_pending_adaptation_updates_plan_and_creates_revision(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    adaptation, base_revision = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(tasks[1]),
                    "reason": "The estimate is too short.",
                    "estimated_duration_minutes": 90,
                }
            ]
        ),
    )
    provider_calls = 0

    def fail_if_provider_is_built() -> None:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("Accept must not construct an LLM provider")

    app.dependency_overrides[get_adaptation_provider_factory] = (
        fail_if_provider_is_built
    )
    try:
        response = asyncio.run(post_accept(goal.id, adaptation.id))
    finally:
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    assert provider_calls == 0
    assert response.json()["status"] == "accepted"
    assert response.json()["applied_change_count"] == 1
    assert response.json()["revision_number"] == 2
    assert response.json()["reviewed_at"] is not None
    db_session.refresh(tasks[1])
    db_session.refresh(adaptation)
    assert tasks[1].estimated_duration_minutes == 90
    assert adaptation.status == AdaptationStatus.ACCEPTED
    assert adaptation.reviewed_at is not None
    revisions = list(
        db_session.scalars(
            select(PlanRevision).order_by(PlanRevision.revision_number)
        )
    )
    assert len(revisions) == 2
    assert revisions[1].base_revision_id == base_revision.id
    assert revisions[1].adaptation_id == adaptation.id
    assert revisions[1].snapshot["stages"][0]["missions"][0]["tasks"][1][
        "estimated_duration_minutes"
    ] == 90


def test_accept_add_task_inserts_and_normalizes_order_indexes(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, mission, tasks = persist_plan(
        db_session, authenticated_user_id
    )
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "add_task",
                    "target": {
                        key: value
                        for key, value in target(tasks[0]).items()
                        if not key.startswith("task_")
                    },
                    "reason": "Add a validation prerequisite.",
                    "insert_after_task_order_index": 0,
                    "task": {
                        "title": "Define validation rules",
                        "description": "List invalid request cases.",
                        "estimated_duration_minutes": 20,
                        "xp_reward": 10,
                    },
                }
            ]
        ),
    )

    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 200
    persisted = list(
        db_session.scalars(
            select(Task)
            .where(Task.mission_id == mission.id)
            .order_by(Task.order_index)
        )
    )
    assert [task.title for task in persisted] == [
        "Design endpoint",
        "Define validation rules",
        "Implement endpoint",
        "Test endpoint",
    ]
    assert [task.order_index for task in persisted] == [0, 1, 2, 3]
    assert persisted[1].status == PlanningStatus.PENDING
    assert persisted[1].estimated_difficulty is None


def test_accept_reorder_task_moves_within_mission_and_normalizes_indexes(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, mission, tasks = persist_plan(
        db_session, authenticated_user_id
    )
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "reorder_task",
                    "target": target(tasks[2]),
                    "reason": "Testing should guide implementation.",
                    "destination_order_index": 0,
                }
            ]
        ),
    )

    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 200
    persisted = list(
        db_session.scalars(
            select(Task)
            .where(Task.mission_id == mission.id)
            .order_by(Task.order_index)
        )
    )
    assert [task.title for task in persisted] == [
        "Test endpoint",
        "Design endpoint",
        "Implement endpoint",
    ]
    assert [task.order_index for task in persisted] == [0, 1, 2]


def test_accept_split_replace_and_adjust_difficulty(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, stage, first_mission, first_tasks = persist_plan(
        db_session, authenticated_user_id
    )
    second_mission = Mission(
        stage=stage, title="Deployment", order_index=1
    )
    replace_target = Task(
        mission=second_mission,
        title="Read deployment docs",
        order_index=0,
        estimated_duration_minutes=30,
        estimated_difficulty="easy",
        xp_reward=10,
    )
    difficulty_target = Task(
        mission=second_mission,
        title="Deploy service",
        order_index=1,
        estimated_duration_minutes=60,
        estimated_difficulty="normal",
        xp_reward=15,
    )
    db_session.add(second_mission)
    db_session.commit()
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "split_task",
                    "target": target(first_tasks[1]),
                    "reason": "The implementation is too broad.",
                    "replacement_tasks": [
                        {
                            "title": "Implement request validation",
                            "description": None,
                            "estimated_duration_minutes": 30,
                            "xp_reward": 10,
                        },
                        {
                            "title": "Implement response mapping",
                            "description": None,
                            "estimated_duration_minutes": 30,
                            "xp_reward": 10,
                        },
                    ],
                },
                {
                    "type": "replace_task",
                    "target": {
                        **target(replace_target),
                        "mission_order_index": 1,
                        "mission_title": "Deployment",
                    },
                    "reason": "Hands-on preparation is more useful.",
                    "replacement": {
                        "title": "Prepare deployment checklist",
                        "description": "Capture required configuration.",
                        "estimated_duration_minutes": 45,
                        "xp_reward": 15,
                    },
                },
                {
                    "type": "adjust_task_difficulty",
                    "target": {
                        **target(difficulty_target),
                        "mission_order_index": 1,
                        "mission_title": "Deployment",
                    },
                    "reason": "Deployment needs a safer target.",
                    "proposed_difficulty": "easy",
                },
            ]
        ),
    )

    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 200
    first_titles = list(
        db_session.scalars(
            select(Task.title)
            .where(Task.mission_id == first_mission.id)
            .order_by(Task.order_index)
        )
    )
    assert first_titles == [
        "Design endpoint",
        "Implement request validation",
        "Implement response mapping",
        "Test endpoint",
    ]
    db_session.refresh(replace_target)
    db_session.refresh(difficulty_target)
    assert replace_target.title == "Prepare deployment checklist"
    assert replace_target.estimated_duration_minutes == 45
    assert replace_target.estimated_difficulty is None
    assert difficulty_target.estimated_difficulty == "easy"


@pytest.mark.parametrize("reviewed_status", ["accepted", "rejected"])
def test_accept_requires_pending_adaptation(
    reviewed_status: str,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(tasks[0]),
                    "reason": "Change duration.",
                    "estimated_duration_minutes": 50,
                }
            ]
        ),
        status=AdaptationStatus(reviewed_status),
    )

    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 409
    db_session.refresh(tasks[0])
    assert tasks[0].estimated_duration_minutes == 30


def test_second_accept_returns_conflict_without_second_revision(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(tasks[0]),
                    "reason": "Change duration.",
                    "estimated_duration_minutes": 50,
                }
            ]
        ),
    )

    first = asyncio.run(post_accept(goal.id, adaptation.id))
    second = asyncio.run(post_accept(goal.id, adaptation.id))

    assert first.status_code == 200
    assert second.status_code == 409
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 2
    )


def test_accept_enforces_user_and_path_goal_ownership(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    foreign_goal, _, _, foreign_tasks = persist_plan(db_session, uuid4())
    foreign_adaptation, _ = persist_adaptation(
        db_session,
        foreign_goal,
        proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(foreign_tasks[0]),
                    "reason": "Change duration.",
                    "estimated_duration_minutes": 50,
                }
            ]
        ),
    )
    owned_goal, _, _, _ = persist_plan(db_session, authenticated_user_id)

    foreign_user_response = asyncio.run(
        post_accept(foreign_goal.id, foreign_adaptation.id)
    )
    wrong_goal_response = asyncio.run(
        post_accept(owned_goal.id, foreign_adaptation.id)
    )

    assert foreign_user_response.status_code == 404
    assert foreign_user_response.json() == {"detail": "Goal not found"}
    assert wrong_goal_response.status_code == 404
    assert wrong_goal_response.json() == {"detail": "Adaptation not found"}


def test_accept_rejects_obsolete_or_changed_targets(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    payload = proposal(
        [
            {
                "type": "adjust_task_duration",
                "target": target(tasks[0]),
                "reason": "Change duration.",
                "estimated_duration_minutes": 50,
            }
        ]
    )
    obsolete_adaptation, base = persist_adaptation(
        db_session, goal, payload
    )
    create_plan_revision(db_session, goal.id, base_revision=base)
    db_session.commit()

    obsolete_response = asyncio.run(
        post_accept(goal.id, obsolete_adaptation.id)
    )
    assert obsolete_response.status_code == 409

    current_adaptation, _ = persist_adaptation(db_session, goal, payload)
    tasks[0].title = "Renamed Task"
    db_session.commit()
    changed_response = asyncio.run(
        post_accept(goal.id, current_adaptation.id)
    )
    assert changed_response.status_code == 409
    db_session.refresh(current_adaptation)
    assert current_adaptation.status == AdaptationStatus.PENDING


def test_accept_does_not_change_resolved_task_or_feedback(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    task = tasks[0]
    task.status = PlanningStatus.COMPLETED
    task.difficulty_feedback = "difficult"
    task.feedback_text = "Historical feedback"
    task.estimated_difficulty = "normal"
    task.resolved_at = datetime.now(UTC)
    xp_reward = task.xp_reward
    db_session.commit()
    db_session.refresh(task)
    resolved_at = task.resolved_at
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "adjust_task_difficulty",
                    "target": target(task),
                    "reason": "Change planned difficulty.",
                    "proposed_difficulty": "easy",
                }
            ]
        ),
    )

    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 409
    db_session.refresh(task)
    db_session.refresh(adaptation)
    assert task.estimated_difficulty == "normal"
    assert task.difficulty_feedback == "difficult"
    assert task.feedback_text == "Historical feedback"
    assert task.resolved_at == resolved_at
    assert task.xp_reward == xp_reward
    assert adaptation.status == AdaptationStatus.PENDING


def test_accept_rejects_legacy_adaptation_without_base_revision(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    legacy_adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=None,
        proposal=proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(tasks[0]),
                    "reason": "Change duration.",
                    "estimated_duration_minutes": 50,
                }
            ]
        ),
    )
    db_session.add(legacy_adaptation)
    db_session.commit()

    response = asyncio.run(post_accept(goal.id, legacy_adaptation.id))

    assert response.status_code == 409
    db_session.refresh(tasks[0])
    db_session.refresh(legacy_adaptation)
    assert tasks[0].estimated_duration_minutes == 30
    assert legacy_adaptation.status == AdaptationStatus.PENDING


def test_accept_rolls_back_all_changes_when_revision_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal, _, _, tasks = persist_plan(db_session, authenticated_user_id)
    adaptation, _ = persist_adaptation(
        db_session,
        goal,
        proposal(
            [
                {
                    "type": "adjust_task_duration",
                    "target": target(tasks[0]),
                    "reason": "Change duration.",
                    "estimated_duration_minutes": 50,
                }
            ]
        ),
    )

    def fail_revision(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Deliberate revision failure")

    monkeypatch.setattr(
        acceptance_service, "create_plan_revision", fail_revision
    )
    response = asyncio.run(post_accept(goal.id, adaptation.id))

    assert response.status_code == 500
    db_session.refresh(tasks[0])
    db_session.refresh(adaptation)
    assert tasks[0].estimated_duration_minutes == 30
    assert adaptation.status == AdaptationStatus.PENDING
    assert adaptation.reviewed_at is None
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 1
    )
