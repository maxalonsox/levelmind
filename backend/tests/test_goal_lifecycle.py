import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.main import app
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task


async def request(method: str, path: str) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path)


def persist_goal(
    db: Session,
    user_id: UUID,
    *,
    status: str = "active",
    created_at: datetime | None = None,
) -> Goal:
    goal = Goal(
        user_id=user_id,
        title=f"Goal {uuid4()}",
        current_situation="Current situation",
        expected_outcome="Expected outcome",
        status=status,
    )
    if created_at is not None:
        goal.created_at = created_at
    db.add(goal)
    db.commit()
    return goal


def test_owner_recovers_latest_active_goal_deterministically(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    now = datetime.now(UTC)
    older = persist_goal(
        db_session,
        authenticated_user_id,
        created_at=now - timedelta(days=1),
    )
    latest = persist_goal(
        db_session,
        authenticated_user_id,
        created_at=now,
    )
    persist_goal(db_session, authenticated_user_id, status="archived")
    persist_goal(db_session, uuid4(), created_at=now + timedelta(days=1))

    response = asyncio.run(request("GET", "/goals/active"))

    assert response.status_code == 200
    assert response.json()["id"] == str(latest.id)
    assert response.json()["status"] == "active"
    assert response.json()["id"] != str(older.id)


def test_active_goal_returns_404_without_owned_active_goal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    persist_goal(db_session, authenticated_user_id, status="archived")
    persist_goal(db_session, uuid4())

    response = asyncio.run(request("GET", "/goals/active"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Active goal not found"}


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/goals/active"), ("DELETE", f"/goals/{uuid4()}")],
)
def test_goal_lifecycle_endpoints_require_bearer_authentication(
    method: str,
    path: str,
) -> None:
    response = asyncio.run(request(method, path))

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid or missing authentication credentials"
    }


def test_owner_deletes_goal_and_all_related_rows(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    goal = persist_goal(db_session, authenticated_user_id)
    stage = Stage(goal_id=goal.id, title="Stage", order_index=0)
    mission = Mission(title="Mission", order_index=0)
    task = Task(title="Task", order_index=0)
    mission.tasks.append(task)
    stage.missions.append(mission)
    revision = PlanRevision(
        goal_id=goal.id,
        revision_number=1,
        snapshot={"stages": []},
    )
    db_session.add_all([stage, revision])
    db_session.flush()
    adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=revision.id,
        proposal={
            "decision": "no_change",
            "summary": "Summary",
            "rationale": "Rationale",
            "changes": [],
        },
    )
    memory = MemoryEntry(
        user_id=authenticated_user_id,
        goal_id=goal.id,
        memory_type="observed",
        key="task_execution",
        value={"result": "completed"},
        source_type="task",
        source_id=task.id,
        confidence=1,
    )
    db_session.add_all([adaptation, memory])
    db_session.commit()

    response = asyncio.run(request("DELETE", f"/goals/{goal.id}"))

    assert response.status_code == 204
    assert response.content == b""
    for model in (
        Goal,
        Stage,
        Mission,
        Task,
        PlanRevision,
        PlanAdaptation,
        MemoryEntry,
    ):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    active_response = asyncio.run(request("GET", "/goals/active"))
    assert active_response.status_code == 404


@pytest.mark.parametrize("goal_kind", ["foreign", "missing"])
def test_delete_hides_foreign_and_missing_goals(
    goal_kind: str,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal_id = (
        persist_goal(db_session, uuid4()).id
        if goal_kind == "foreign"
        else uuid4()
    )

    response = asyncio.run(request("DELETE", f"/goals/{goal_id}"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}
    if goal_kind == "foreign":
        assert db_session.get(Goal, goal_id) is not None


def test_delete_rolls_back_memory_removal_when_goal_delete_fails(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    memory = MemoryEntry(
        user_id=authenticated_user_id,
        goal_id=goal.id,
        memory_type="observed",
        key="task_execution",
        value={"result": "completed"},
        source_type="task",
        source_id=uuid4(),
        confidence=1,
    )
    db_session.add(memory)
    db_session.commit()

    def fail_delete(_mapper: Any, _connection: Any, _target: Goal) -> None:
        raise RuntimeError("Deliberate delete failure")

    event.listen(Goal, "before_delete", fail_delete)
    try:
        with pytest.raises(RuntimeError, match="Deliberate delete failure"):
            asyncio.run(request("DELETE", f"/goals/{goal.id}"))
    finally:
        event.remove(Goal, "before_delete", fail_delete)

    assert db_session.get(Goal, goal.id) is not None
    assert db_session.get(MemoryEntry, memory.id) is not None
